from __future__ import annotations
import json
import logging
import math
import re
from dataclasses import dataclass, field
from typing import Optional
import fitz 
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from google import genai
from google.genai import types
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from pydantic import ValidationError, BaseModel
from .models import Course, Module, Lesson, Content, Quiz, Question, Option
from .schemas import (
    CourseOutlineSchema,
    LessonSchema,
    QuizSchema,
)

logger = logging.getLogger(__name__)


MIN_QUIZ_QUESTIONS = getattr(settings, "LMS_MIN_QUIZ_QUESTIONS", 20)
QUESTIONS_PER_LESSON = getattr(settings, "LMS_QUESTIONS_PER_LESSON", 2)
MAX_PDF_PAGES = getattr(settings, "LMS_MAX_PDF_PAGES", 400)
GEMINI_MODEL = getattr(settings, "GEMINI_MODEL_NAME", "gemini-3.6-flash")
CHARS_PER_CHUNK = 24000  # conservative slice size per Gemini call


class PDFExtractionError(Exception):
    """Raised when PDF text/image extraction fails outright."""


class CourseGenerationError(Exception):
    """Raised when Gemini output fails validation after retries."""


class GeminiTransientError(Exception):
    """Wraps transient Gemini/API errors so tenacity knows to retry them."""


@dataclass
class ExtractedPage:
    page_number: int
    text: str
    image_bytes_list: list = field(default_factory=list)


@dataclass
class ExtractionResult:
    pages: list  # list[ExtractedPage]
    full_text: str
    pages_processed: int
    images_extracted: int


class ModulePackageSchema(BaseModel):
    lessons: list[LessonSchema]
    quiz: Optional[QuizSchema] = None


class PDFCourseExtractorService:

    # ------------------------------------------------------------------
    # Extraction
    # ------------------------------------------------------------------
    @staticmethod
    def extract(pdf_file) -> ExtractionResult:
        try:
            pdf_bytes = pdf_file.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        except Exception as e:
            logger.error(f"Failed to open PDF: {e}")
            raise PDFExtractionError("The uploaded file could not be opened as a valid PDF.")

        total_pages = doc.page_count
        pages_to_process = min(total_pages, MAX_PDF_PAGES)
        if total_pages > MAX_PDF_PAGES:
            logger.warning(
                f"PDF has {total_pages} pages; processing first {MAX_PDF_PAGES} "
                f"per LMS_MAX_PDF_PAGES setting."
            )

        pages: list[ExtractedPage] = []
        images_extracted = 0
        full_text_parts = []

        for page_num in range(pages_to_process):
            page = doc.load_page(page_num)
            page_text = page.get_text("text") or ""

            image_bytes_list = []
            for img in page.get_images(full=True):
                xref = img[0]
                try:
                    base_image = doc.extract_image(xref)
                    img_bytes = base_image.get("image")
                    if img_bytes and len(img_bytes) > 8000:
                        image_bytes_list.append(
                            (img_bytes, base_image.get("ext", "png"))
                        )
                        images_extracted += 1
                except Exception as img_err:
                    logger.debug(f"Skipping unreadable image on page {page_num}: {img_err}")

            pages.append(
                ExtractedPage(
                    page_number=page_num + 1,
                    text=page_text,
                    image_bytes_list=image_bytes_list,
                )
            )
            full_text_parts.append(page_text)

        doc.close()
        full_text = "\n".join(full_text_parts)

        if not full_text.strip() and images_extracted == 0:
            raise PDFExtractionError(
                "The uploaded PDF contains no extractable text or images. "
                "If this is a scanned document, OCR it before uploading."
            )

        return ExtractionResult(
            pages=pages,
            full_text=full_text,
            pages_processed=pages_to_process,
            images_extracted=images_extracted,
        )

    # ------------------------------------------------------------------
    # FIX #2: Dynamic Backoff Capable Gemini Call Wrapper
    # ------------------------------------------------------------------
    @staticmethod
    @retry(
        retry=retry_if_exception_type(GeminiTransientError),
        wait=wait_exponential(multiplier=2, min=5, max=65),  # Increased max ceiling to 65s
        stop=stop_after_attempt(6),                          # Allow more attempts for rate-limit recovery
        reraise=True,
    )
    def _call_gemini(client, prompt: str) -> dict:
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.25,
                    max_output_tokens=8192,
                ),
            )
        except Exception as e:
            err_msg = str(e)
            transient_markers = ("429", "500", "502", "503", "504", "deadline", "timeout", "resource_exhausted")
            
            if any(m in err_msg.lower() for m in transient_markers):
                # Log detailed rate-limit wait notification
                logger.warning(f"Transient Gemini API limit hit: {err_msg}. Retrying with exponential backoff...")
                raise GeminiTransientError(err_msg) from e
            
            logger.error(f"Non-retryable Gemini error: {e}")
            raise CourseGenerationError(f"Gemini generation failed: {e}") from e

        if not response.text:
            raise GeminiTransientError("Empty response body from Gemini.")

        try:
            return json.loads(response.text)
        except json.JSONDecodeError as e:
            raise GeminiTransientError(f"Malformed JSON from Gemini: {e}") from e

    # ------------------------------------------------------------------
    # Stage 1: Outline
    # ------------------------------------------------------------------
    @classmethod
    def generate_outline(cls, client, full_text: str, custom_title: Optional[str]) -> CourseOutlineSchema:
        prompt = f"""
        You are an expert instructional designer building a course outline
        for an enterprise LMS. Analyze the source text and produce ONLY the
        structural skeleton — module and lesson TITLES with short
        descriptions. Do NOT write lesson content yet.

        Requirements:
        - Title: concise course title (or use '{custom_title}' if provided and non-empty).
        - 4-8 modules, ordered logically by topic progression in the source.
        - Each module: 2-5 lessons, titled specifically enough that a
          content-writer could produce a full lesson from the title alone.

        Return ONLY valid JSON:
        {{
            "title": "string",
            "description": "<p>one paragraph HTML</p>",
            "category": "beginner|expert|professional",
            "modules": [
                {{
                    "title": "string", "description": "<p>...</p>", "order": 1,
                    "lessons": [
                        {{"title": "string", "description": "<p>...</p>", "order": 1, "contents": [{{"title":"placeholder","content_type":"text","text_content":"","diagram_code":"","order":1}}]}}
                    ]
                }}
            ]
        }}

        Source text (may be partial for very large documents):
        {full_text[:CHARS_PER_CHUNK]}
        """
        raw = cls._call_gemini(client, prompt)
        try:
            return CourseOutlineSchema.model_validate(raw)
        except ValidationError as e:
            raise CourseGenerationError(f"Outline validation failed: {e}") from e

    # ------------------------------------------------------------------
    # FIX #1: Merged Per-Module Content + Quiz Generation (1 Call per Module)
    # ------------------------------------------------------------------
    @classmethod
    def generate_module_package(
        cls, client, module_title: str, lesson_titles: list, source_slice: str, questions_needed: int, generate_quiz: bool = True
    ) -> ModulePackageSchema:
        lesson_list_str = "\n".join(f"- {t}" for t in lesson_titles)
        
        quiz_instructions = ""
        quiz_json_schema = ""
        
        if generate_quiz:
            quiz_instructions = f"""
            ALSO generate exactly {questions_needed} multiple-choice quiz questions testing understanding 
            of this module.
            - Each question: 4 options, exactly one marked is_correct: true.
            - Mix recall, applied-scenario, and conceptual questions.
            """
            quiz_json_schema = """,
            "quiz": {
                "title": "Quiz Title",
                "pass_percentage": 70,
                "questions": [
                    {"text": "string", "is_multi_select": false, "options": [{"text": "string", "is_correct": true}]}
                ]
            }"""

        prompt = f"""
        You are writing detailed lesson content and assessments for the module "{module_title}" 
        in an enterprise LMS course. The module has these lessons:
        {lesson_list_str}

        Requirements for lessons:
        - For EACH lesson, produce one or more content blocks.
        - At least one block with content_type "text": detailed HTML reading material (<p>, <ul>, <strong>, <h4>) 
          covering the lesson thoroughly (200-400 words).
        - IF the lesson describes a process, workflow, decision tree, hierarchy, or architecture, ALSO add a block 
          with content_type "diagram" using valid Mermaid.js syntax.

        {quiz_instructions}

        Return ONLY valid JSON matching:
        {{
            "lessons": [
                {{
                    "title": "must match one of the lesson titles above exactly",
                    "contents": [
                        {{"title": "string", "content_type": "text", "text_content": "<p>...</p>", "diagram_code": "", "order": 1}},
                        {{"title": "string", "content_type": "diagram", "text_content": "", "diagram_code": "flowchart TD\\nA-->B", "order": 2}}
                    ]
                }}
            ]{quiz_json_schema}
        }}

        Relevant source text for this module:
        {source_slice[:CHARS_PER_CHUNK]}
        """
        raw = cls._call_gemini(client, prompt)
        try:
            return ModulePackageSchema.model_validate(raw)
        except ValidationError as e:
            raise CourseGenerationError(f"Module packaging failed for '{module_title}': {e}") from e

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------
    @classmethod
    def build_course_from_pdf(
        cls,
        instructor,
        pdf_file,
        custom_title: Optional[str] = None,
        generate_quiz: bool = True,
        min_questions: Optional[int] = None,
        progress_callback=None,
    ) -> Course:
        min_questions = min_questions or MIN_QUIZ_QUESTIONS

        def _progress(status, pct):
            if progress_callback:
                progress_callback(status, pct)

        client = genai.Client(api_key=settings.GEMINI_API_KEY)

        _progress("extracting_text", 5)
        extraction = cls.extract(pdf_file)

        _progress("generating_outline", 15)
        outline = cls.generate_outline(client, extraction.full_text, custom_title)

        total_lessons = sum(len(m.lessons) for m in outline.modules)
        if total_lessons == 0:
            raise CourseGenerationError("Generated outline contained no lessons.")

        target_questions = max(min_questions, total_lessons * QUESTIONS_PER_LESSON)
        questions_per_module = max(2, math.ceil(target_questions / max(1, len(outline.modules))))

        chunk_size = max(1, len(extraction.pages) // max(1, len(outline.modules)))

        with transaction.atomic():
            course = Course.objects.create(
                title=outline.title,
                description=outline.description,
                category=outline.category,
                instructor=instructor,
                is_published=False,
            )

            total_questions_generated = 0
            stage_pct = 20
            pct_per_module = 75 / max(1, len(outline.modules))

            for m_idx, mod in enumerate(outline.modules):
                module_obj = Module.objects.create(
                    course=course,
                    title=mod.title,
                    description=mod.description,
                    order=mod.order or (m_idx + 1),
                )

                lesson_titles = [l.title for l in mod.lessons]
                source_start = m_idx * chunk_size
                source_end = min(len(extraction.pages), source_start + chunk_size + 1)
                source_slice = "\n".join(
                    p.text for p in extraction.pages[source_start:source_end]
                )

                _progress("generating_content_and_quiz", int(stage_pct))
                
                try:
                    # Single merged API Call per module
                    pkg = cls.generate_module_package(
                        client, 
                        mod.title, 
                        lesson_titles, 
                        source_slice or extraction.full_text,
                        questions_per_module,
                        generate_quiz=generate_quiz
                    )
                    detailed_lessons = pkg.lessons
                    module_quiz = pkg.quiz
                except (GeminiTransientError, CourseGenerationError) as e:
                    logger.error(f"Module package generation failed for '{mod.title}': {e}")
                    detailed_lessons = []
                    module_quiz = None

                detailed_by_title = {l.title: l for l in detailed_lessons}

                for l_idx, lesson_outline in enumerate(mod.lessons, start=1):
                    lesson_obj = Lesson.objects.create(
                        module=module_obj,
                        title=lesson_outline.title,
                        description=lesson_outline.description,
                        order=lesson_outline.order or l_idx,
                    )

                    detailed = detailed_by_title.get(lesson_outline.title)
                    content_blocks = detailed.contents if detailed else lesson_outline.contents

                    for c_idx, content in enumerate(content_blocks, start=1):
                        Content.objects.create(
                            lesson=lesson_obj,
                            title=content.title,
                            content_type=content.content_type,
                            text_content=content.text_content,
                            diagram_code=content.diagram_code or None,
                            order=content.order or c_idx,
                        )

                    page_slice = extraction.pages[source_start:source_end]
                    for page in page_slice:
                        if page.image_bytes_list:
                            img_bytes, ext = page.image_bytes_list[0]
                            img_content = Content(
                                lesson=lesson_obj,
                                title=f"Figure (source p.{page.page_number})",
                                content_type="image",
                                order=len(content_blocks) + 1,
                                source_page_number=page.page_number,
                            )
                            img_content.image.save(
                                f"p{page.page_number}_lesson{lesson_obj.pk}.{ext}",
                                ContentFile(img_bytes),
                                save=True,
                            )
                            break  

                if generate_quiz and module_quiz:
                    quiz_obj, _ = Quiz.objects.get_or_create(
                        course=course,
                        defaults=dict(
                            title=f"{course.title} Final Assessment",
                            description=f"<p>Assessment quiz for {course.title}</p>",
                            pass_percentage=module_quiz.pass_percentage,
                            created_by=instructor,
                        ),
                    )
                    existing_question_count = quiz_obj.questions.count()
                    for q_offset, q in enumerate(module_quiz.questions, start=1):
                        question_obj = Question.objects.create(
                            quiz=quiz_obj,
                            text=q.text,
                            is_multi_select=q.is_multi_select,
                            order=existing_question_count + q_offset,
                        )
                        for opt in q.options:
                            Option.objects.create(
                                question=question_obj,
                                text=opt.text,
                                is_correct=opt.is_correct,
                            )
                        total_questions_generated += 1

                stage_pct += pct_per_module

            _progress("completed", 100)
            logger.info(
                f"Course '{course.title}' built: {len(outline.modules)} modules, "
                f"{total_lessons} lessons, {total_questions_generated} quiz questions, "
                f"{extraction.images_extracted} images extracted from "
                f"{extraction.pages_processed} pages."
            )

        return course
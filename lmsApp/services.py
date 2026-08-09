from __future__ import annotations
import io
import json
import logging
import math
import re
import time
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
from pydantic import ValidationError
 
from .models import Course, Module, Lesson, Content, Quiz, Question, Option
from .schemas import (
    CourseOutlineSchema,
    LessonSchema,
    QuizSchema,
    ModuleGenerationSchema,
)
 
logger = logging.getLogger(__name__)
 
MIN_QUIZ_QUESTIONS = getattr(settings, "LMS_MIN_QUIZ_QUESTIONS", 20)
QUESTIONS_PER_LESSON = getattr(settings, "LMS_QUESTIONS_PER_LESSON", 2)
MAX_PDF_PAGES = getattr(settings, "LMS_MAX_PDF_PAGES", 400)
GEMINI_MODEL = getattr(settings, "LMS_GEMINI_MODEL", "gemini-3.6-flash")
CHARS_PER_CHUNK = 24000 
 
 
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
                    # Skip tiny/likely-decorative images (icons, bullets, logos)
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
    # Gemini call wrapper with retry
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_retry_delay_seconds(error_str: str) -> Optional[float]:
        """
        Google's 429 error body includes a RetryInfo block with the exact
        number of seconds it wants you to wait, e.g. 'retryDelay': '59s'.
        Blind exponential backoff (which our previous version used) ignores
        this and just wastes retry attempts hammering a quota that hasn't
        reset yet. Parse it out and use it directly when present.
        """
        match = re.search(r"'retryDelay':\s*'(\d+(?:\.\d+)?)s'", error_str)
        if match:
            return float(match.group(1))
        return None
 
    @classmethod
    @retry(
        retry=retry_if_exception_type(GeminiTransientError),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _call_gemini(cls, client, prompt: str, response_schema_hint: str = "") -> dict:
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
            error_str = str(e)
            lower = error_str.lower()

            if "429" in error_str or "resource_exhausted" in lower:
                delay = cls._extract_retry_delay_seconds(error_str)
                if delay is not None:
                    capped_delay = min(delay, 90)
                    logger.warning(
                        f"Gemini quota exhausted; sleeping {capped_delay:.0f}s "
                        f"per Google's RetryInfo before retrying."
                    )
                    time.sleep(capped_delay)
                raise GeminiTransientError(error_str) from e
 
            transient_markers = ("500", "502", "503", "504", "deadline", "timeout")
            if any(m in lower for m in transient_markers):
                raise GeminiTransientError(error_str) from e
 
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
    # Stage 2+3 (merged): per-module content AND quiz in one call
    # ------------------------------------------------------------------
    @classmethod
    def generate_module_content_and_quiz(
        cls,
        client,
        module_title: str,
        lesson_titles: list,
        source_slice: str,
        questions_needed: int,
    ) -> ModuleGenerationSchema:
        lesson_list_str = "\n".join(f"- {t}" for t in lesson_titles)
        prompt = f"""
        You are building one module, "{module_title}", of an enterprise LMS
        course. The module has these lessons:
        {lesson_list_str}
 
        PART 1 — LESSON CONTENT. For EACH lesson, produce one or more
        content blocks:
        - At least one block with content_type "text": detailed HTML reading
          material (<p>, <ul>, <strong>, <h4>) covering the lesson thoroughly
          (aim for 200-400 words per lesson).
        - IF the lesson describes a process, workflow, decision tree,
          hierarchy, system architecture, or sequence of events, ALSO add a
          block with content_type "diagram" whose text_content is empty and
          whose diagram_code contains valid Mermaid.js syntax (flowchart TD,
          sequenceDiagram, or graph, as appropriate) representing it visually.
          Do not force a diagram where the content is not inherently
          structural — omit it rather than invent one.
 
        PART 2 — QUIZ. Generate exactly {questions_needed} multiple-choice
        questions testing understanding of THIS module's lessons:
        - Each question: 4 options, exactly one marked is_correct: true.
        - Mix recall, applied-scenario, and conceptual questions — do not
          make them all simple definition lookups.
        - Vary difficulty across the set.
        - Base questions only on the lesson content you just wrote plus the
          source text below, not on other modules.
 
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
            ],
            "quiz": {{
                "title": "{module_title} Quiz",
                "pass_percentage": 70,
                "questions": [
                    {{"text": "string", "is_multi_select": false,
                      "options": [{{"text":"string","is_correct":true}}, ...]}}
                ]
            }}
        }}
 
        Relevant source text for this module:
        {source_slice[:CHARS_PER_CHUNK]}
        """
        raw = cls._call_gemini(client, prompt)
        lessons_raw = raw.get("lessons", [])
        validated_lessons = []
        for l in lessons_raw:
            try:
                validated_lessons.append(LessonSchema.model_validate({**l, "order": 1}))
            except ValidationError as e:
                logger.warning(f"Skipping malformed lesson content block: {e}")
 
        quiz_raw = raw.get("quiz")
        validated_quiz = None
        if quiz_raw:
            try:
                validated_quiz = QuizSchema.model_validate(quiz_raw)
            except ValidationError as e:
                logger.warning(f"Quiz portion invalid for module '{module_title}': {e}")
 
        if not validated_lessons and validated_quiz is None:
            raise CourseGenerationError(
                f"Merged generation for module '{module_title}' produced neither "
                f"valid lessons nor a valid quiz."
            )
 
        return ModuleGenerationSchema(
            lessons=validated_lessons,
            quiz=validated_quiz or QuizSchema(questions=[]),
        )
 
    # ------------------------------------------------------------------
    # Stage 3b: quiz-only generation, used ONLY for the top-up pass at
    # the end if the merged per-module calls landed short of the floor.
    # ------------------------------------------------------------------
    @classmethod
    def generate_module_quiz(
        cls, client, module_title: str, lesson_titles: list, questions_needed: int
    ) -> QuizSchema:
        prompt = f"""
        Generate exactly {questions_needed} multiple-choice quiz questions
        testing understanding of the module "{module_title}", which covers
        these lessons: {', '.join(lesson_titles)}.
 
        Requirements:
        - Each question: 4 options, exactly one marked is_correct: true.
        - Mix recall, applied-scenario, and conceptual questions — do not
          make them all simple definition lookups.
        - Vary difficulty across the set.
 
        Return ONLY valid JSON:
        {{
            "title": "Quiz title",
            "pass_percentage": 70,
            "questions": [
                {{"text": "string", "is_multi_select": false,
                  "options": [{{"text":"string","is_correct":true}}, ...]}}
            ]
        }}
        """
        raw = cls._call_gemini(client, prompt)
        try:
            return QuizSchema.model_validate(raw)
        except ValidationError as e:
            raise CourseGenerationError(f"Quiz validation failed for module '{module_title}': {e}") from e
 
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
        """
        progress_callback(status: str, percentage: int) is called between
        stages so a Celery task can update a CourseImportJob row for
        real-time status in the UI.
        """
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
            pct_per_module = 60 / max(1, len(outline.modules))
 
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
 
                _progress("generating_content", int(stage_pct))
                try:
                    module_result = cls.generate_module_content_and_quiz(
                        client,
                        mod.title,
                        lesson_titles,
                        source_slice or extraction.full_text,
                        questions_per_module,
                    )
                    detailed_lessons = module_result.lessons
                    module_quiz = module_result.quiz
                except (GeminiTransientError, CourseGenerationError) as e:
                    logger.error(f"Content+quiz generation failed for module '{mod.title}': {e}")
                    detailed_lessons = []
                    module_quiz = None
 
                detailed_by_title = {l.title: l for l in detailed_lessons}
 
                lesson_objs = []
                for l_idx, lesson_outline in enumerate(mod.lessons, start=1):
                    lesson_obj = Lesson.objects.create(
                        module=module_obj,
                        title=lesson_outline.title,
                        description=lesson_outline.description,
                        order=lesson_outline.order or l_idx,
                    )
                    lesson_objs.append(lesson_obj)
 
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
 
                if generate_quiz and module_quiz and module_quiz.questions:
                    _progress("generating_quiz", int(stage_pct + pct_per_module / 2))
                    try:
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
                    except Exception as e:
                        logger.error(f"Failed to persist quiz questions for module '{mod.title}': {e}")
 
                stage_pct += pct_per_module
 
            if generate_quiz and total_questions_generated < min_questions:
                shortfall = min_questions - total_questions_generated
                try:
                    quiz_obj = course.quiz
                    topup = cls.generate_module_quiz(
                        client, course.title,
                        [l.title for m in outline.modules for l in m.lessons],
                        shortfall,
                    )
                    existing_question_count = quiz_obj.questions.count()
                    for q_offset, q in enumerate(topup.questions, start=1):
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
                except (CourseGenerationError, Quiz.DoesNotExist) as e:
                    logger.warning(f"Top-up quiz generation skipped: {e}")
 
            _progress("completed", 100)
            logger.info(
                f"Course '{course.title}' built: {len(outline.modules)} modules, "
                f"{total_lessons} lessons, {total_questions_generated} quiz questions, "
                f"{extraction.images_extracted} images extracted from "
                f"{extraction.pages_processed} pages."
            )
 
        return course

    
class ExternalResourceCourseGeneratorService:
    """
    Curates an internal Course from one or more ExternalTrainingResource rows,
    using their metadata (title/description/level/product_area) as TOPICAL
    GUIDANCE ONLY. Every prompt explicitly instructs the model to write
    original material rather than reproduce the source description — this is
    the copyright guardrail; do not remove that instruction when editing
    prompts later.
 
    Reuses PDFCourseExtractorService._call_gemini (retry/backoff/quota
    handling) rather than re-implementing it — if that method's behavior
    changes, this class picks it up automatically.
    """
 
    # ------------------------------------------------------------------
    # Shared helper
    # ------------------------------------------------------------------
    @staticmethod
    def _resource_brief(resource) -> str:
        parts = [
            f"Topic title: {resource.title}",
            f"Source provider: {resource.get_provider_display()} (for context only — do not mention the provider by name in generated content)",
        ]
        if resource.level:
            parts.append(f"Level: {resource.level}")
        if resource.product_area:
            parts.append(f"Product area: {resource.product_area}")
        if resource.description:
            parts.append(
                "Summary — USE THIS ONLY AS TOPICAL DIRECTION, DO NOT COPY OR CLOSELY "
                f"PARAPHRASE ITS WORDING: {resource.description}"
            )
        return "\n".join(parts)
 
    # ------------------------------------------------------------------
    # Mode A: single resource — Gemini designs the module breakdown
    # ------------------------------------------------------------------
    @classmethod
    def generate_outline_from_resource(cls, client, resource, custom_title: Optional[str]) -> CourseOutlineSchema:
        brief = cls._resource_brief(resource)
        prompt = f"""
        You are an expert instructional designer building a course outline for
        an enterprise LMS. You are given a BRIEF describing a training topic.
        Use it only as topical direction — write an entirely original
        module/lesson structure covering the same subject matter in your own
        words. Do not reproduce any wording from the brief.
 
        Requirements:
        - Title: concise course title (or use '{custom_title}' if provided and non-empty).
        - 3-6 modules, ordered logically by topic progression.
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
 
        Topic brief:
        {brief}
        """
        raw = PDFCourseExtractorService._call_gemini(client, prompt)
        try:
            return CourseOutlineSchema.model_validate(raw)
        except ValidationError as e:
            raise CourseGenerationError(f"Outline validation failed: {e}") from e
 
    @classmethod
    def build_course_from_single_resource(
        cls, instructor, resource, custom_title: Optional[str] = None,
        generate_quiz: bool = True, min_questions: Optional[int] = None,
        progress_callback=None,
    ) -> Course:
        min_questions = min_questions or MIN_QUIZ_QUESTIONS
 
        def _progress(status, pct):
            if progress_callback:
                progress_callback(status, pct)
 
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
 
        _progress("generating_outline", 15)
        outline = cls.generate_outline_from_resource(client, resource, custom_title)
 
        total_lessons = sum(len(m.lessons) for m in outline.modules)
        if total_lessons == 0:
            raise CourseGenerationError("Generated outline contained no lessons.")
 
        target_questions = max(min_questions, total_lessons * QUESTIONS_PER_LESSON)
        questions_per_module = max(2, math.ceil(target_questions / max(1, len(outline.modules))))
        brief = cls._resource_brief(resource)
 
        with transaction.atomic():
            course = Course.objects.create(
                title=outline.title, description=outline.description, category=outline.category,
                instructor=instructor, is_published=False, content_origin='external_resource_curated',
            )
            course.source_external_resources.add(resource)
 
            total_questions_generated = 0
            stage_pct = 20
            pct_per_module = 60 / max(1, len(outline.modules))
 
            for m_idx, mod in enumerate(outline.modules):
                module_obj = Module.objects.create(
                    course=course, title=mod.title, description=mod.description,
                    order=mod.order or (m_idx + 1),
                )
                lesson_titles = [l.title for l in mod.lessons]
 
                _progress("generating_content", int(stage_pct))
                try:
                    module_result = PDFCourseExtractorService.generate_module_content_and_quiz(
                        client, mod.title, lesson_titles, brief, questions_per_module,
                    )
                    detailed_lessons = module_result.lessons
                    module_quiz = module_result.quiz
                except (GeminiTransientError, CourseGenerationError) as e:
                    logger.error(f"Content+quiz generation failed for module '{mod.title}': {e}")
                    detailed_lessons, module_quiz = [], None
 
                detailed_by_title = {l.title: l for l in detailed_lessons}
                for l_idx, lesson_outline in enumerate(mod.lessons, start=1):
                    lesson_obj = Lesson.objects.create(
                        module=module_obj, title=lesson_outline.title,
                        description=lesson_outline.description, order=lesson_outline.order or l_idx,
                    )
                    detailed = detailed_by_title.get(lesson_outline.title)
                    content_blocks = detailed.contents if detailed else lesson_outline.contents
                    for c_idx, content in enumerate(content_blocks, start=1):
                        Content.objects.create(
                            lesson=lesson_obj, title=content.title, content_type=content.content_type,
                            text_content=content.text_content, diagram_code=content.diagram_code or None,
                            order=content.order or c_idx,
                        )
 
                if generate_quiz and module_quiz and module_quiz.questions:
                    _progress("generating_quiz", int(stage_pct + pct_per_module / 2))
                    quiz_obj, _ = Quiz.objects.get_or_create(
                        course=course,
                        defaults=dict(
                            title=f"{course.title} Final Assessment", quiz_type='final',
                            description=f"<p>Assessment quiz for {course.title}</p>",
                            pass_percentage=module_quiz.pass_percentage, created_by=instructor,
                        ),
                    )
                    existing_count = quiz_obj.questions.count()
                    for q_offset, q in enumerate(module_quiz.questions, start=1):
                        question_obj = Question.objects.create(
                            quiz=quiz_obj, text=q.text, is_multi_select=q.is_multi_select,
                            order=existing_count + q_offset,
                        )
                        for opt in q.options:
                            Option.objects.create(question=question_obj, text=opt.text, is_correct=opt.is_correct)
                        total_questions_generated += 1
 
                stage_pct += pct_per_module
 
            _progress("completed", 100)
            logger.info(
                f"Course '{course.title}' curated from resource '{resource.title}': "
                f"{len(outline.modules)} modules, {total_lessons} lessons, "
                f"{total_questions_generated} quiz questions."
            )
 
        return course
 
    # ------------------------------------------------------------------
    # Mode B: multiple resources — one module per resource, deterministic
    # ------------------------------------------------------------------
    @classmethod
    def generate_module_from_resource(cls, client, resource, questions_needed: int) -> ModuleGenerationSchema:
        brief = cls._resource_brief(resource)
        prompt = f"""
        You are building ONE module of an enterprise LMS course, covering the
        following topic. Use the brief only as topical direction — write
        entirely original instructional material; do not reproduce its wording.
 
        Module topic: {resource.title}
        {brief}
 
        PART 1 — LESSONS. Decide 2-5 lessons that thoroughly cover this topic.
        For each lesson, produce content blocks:
        - At least one "text" block: detailed HTML reading material (<p>, <ul>,
          <strong>, <h4>), 200-400 words.
        - IF the lesson describes a process, workflow, architecture, or
          sequence, ALSO add a "diagram" block with valid Mermaid.js syntax.
          Omit otherwise.
 
        PART 2 — QUIZ. Generate exactly {questions_needed} multiple-choice
        questions testing understanding of this module (4 options each,
        exactly one correct, mixed difficulty and question type).
 
        Return ONLY valid JSON:
        {{
            "lessons": [
                {{"title": "string", "contents": [
                    {{"title": "string", "content_type": "text", "text_content": "<p>...</p>", "diagram_code": "", "order": 1}}
                ]}}
            ],
            "quiz": {{
                "title": "{resource.title} Knowledge Check", "pass_percentage": 70,
                "questions": [
                    {{"text": "string", "is_multi_select": false,
                      "options": [{{"text":"string","is_correct":true}}, ...]}}
                ]
            }}
        }}
        """
        raw = PDFCourseExtractorService._call_gemini(client, prompt)
 
        validated_lessons = []
        for idx, l in enumerate(raw.get("lessons", []), start=1):
            try:
                validated_lessons.append(LessonSchema.model_validate({**l, "order": idx}))
            except ValidationError as e:
                logger.warning(f"Skipping malformed lesson for resource '{resource.title}': {e}")
 
        validated_quiz = None
        quiz_raw = raw.get("quiz")
        if quiz_raw:
            try:
                validated_quiz = QuizSchema.model_validate(quiz_raw)
            except ValidationError as e:
                logger.warning(f"Quiz invalid for resource '{resource.title}': {e}")
 
        if not validated_lessons and validated_quiz is None:
            raise CourseGenerationError(
                f"Generation for resource '{resource.title}' produced neither valid lessons nor a valid quiz."
            )
 
        return ModuleGenerationSchema(lessons=validated_lessons, quiz=validated_quiz or QuizSchema(questions=[]))
 
    @classmethod
    def build_course_from_resources(
        cls, instructor, resources: list, custom_title: Optional[str] = None,
        generate_quiz: bool = True, generate_module_quizzes: bool = False,
        min_questions: Optional[int] = None, progress_callback=None,
    ) -> Course:
        if not resources:
            raise CourseGenerationError("At least one external resource must be provided.")
        min_questions = min_questions or MIN_QUIZ_QUESTIONS
 
        def _progress(status, pct):
            if progress_callback:
                progress_callback(status, pct)
 
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
 
        title = custom_title or (
            resources[0].title if len(resources) == 1
            else f"{resources[0].title} — Curated Learning Path"
        )
        description = (
            "<p>This course curates the following external training topics into original "
            "internal instructional material: " + ", ".join(r.title for r in resources) + ".</p>"
        )
 
        target_questions = max(min_questions, len(resources) * 2 * QUESTIONS_PER_LESSON)
        questions_per_module = max(2, math.ceil(target_questions / len(resources)))
 
        with transaction.atomic():
            course = Course.objects.create(
                title=title, description=description, category='professional',
                instructor=instructor, is_published=False, content_origin='external_resource_curated',
            )
            course.source_external_resources.set(resources)
 
            total_questions_generated = 0
            stage_pct = 10
            pct_per_module = 80 / len(resources)
 
            for idx, resource in enumerate(resources, start=1):
                _progress(f"generating_content", int(stage_pct))
                module_obj = Module.objects.create(
                    course=course, title=resource.title,
                    description=f"<p>Curated training module based on: {resource.title}</p>",
                    order=idx,
                )
 
                try:
                    module_result = cls.generate_module_from_resource(client, resource, questions_per_module)
                except (GeminiTransientError, CourseGenerationError) as e:
                    logger.error(f"Generation failed for resource '{resource.title}': {e}")
                    module_result = ModuleGenerationSchema(lessons=[], quiz=QuizSchema(questions=[]))
 
                for l_idx, lesson in enumerate(module_result.lessons, start=1):
                    lesson_obj = Lesson.objects.create(
                        module=module_obj, title=lesson.title, description="", order=l_idx,
                    )
                    for c_idx, content in enumerate(lesson.contents, start=1):
                        Content.objects.create(
                            lesson=lesson_obj, title=content.title, content_type=content.content_type,
                            text_content=content.text_content, diagram_code=content.diagram_code or None,
                            order=content.order or c_idx,
                        )
 
                has_questions = module_result.quiz and module_result.quiz.questions
                if generate_module_quizzes and has_questions:
                    # Standalone per-module knowledge check (Quiz.module, quiz_type='module_check')
                    module_quiz_obj = Quiz.objects.create(
                        module=module_obj, quiz_type='module_check',
                        title=f"{module_obj.title} Knowledge Check",
                        description=f"<p>Knowledge check for {module_obj.title}</p>",
                        pass_percentage=70, created_by=instructor,
                    )
                    for q_offset, q in enumerate(module_result.quiz.questions, start=1):
                        question_obj = Question.objects.create(
                            quiz=module_quiz_obj, text=q.text, is_multi_select=q.is_multi_select, order=q_offset,
                        )
                        for opt in q.options:
                            Option.objects.create(question=question_obj, text=opt.text, is_correct=opt.is_correct)
                elif generate_quiz and has_questions:
                    # Roll questions into one course-level final assessment instead
                    quiz_obj, _ = Quiz.objects.get_or_create(
                        course=course,
                        defaults=dict(
                            title=f"{course.title} Final Assessment", quiz_type='final',
                            description=f"<p>Assessment quiz for {course.title}</p>",
                            pass_percentage=module_result.quiz.pass_percentage, created_by=instructor,
                        ),
                    )
                    existing_count = quiz_obj.questions.count()
                    for q_offset, q in enumerate(module_result.quiz.questions, start=1):
                        question_obj = Question.objects.create(
                            quiz=quiz_obj, text=q.text, is_multi_select=q.is_multi_select,
                            order=existing_count + q_offset,
                        )
                        for opt in q.options:
                            Option.objects.create(question=question_obj, text=opt.text, is_correct=opt.is_correct)
                        total_questions_generated += 1
 
                stage_pct += pct_per_module
 
            _progress("completed", 100)
            logger.info(
                f"Course '{course.title}' curated from {len(resources)} resources: "
                f"{len(resources)} modules, {total_questions_generated} final-quiz questions "
                f"({'module checks generated separately' if generate_module_quizzes else 'no module checks'})."
            )
 
        return course
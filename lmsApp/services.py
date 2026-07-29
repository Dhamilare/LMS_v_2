import pypdf
import json
import logging
from google import genai
from google.genai import types
from django.conf import settings
from django.db import transaction
from .models import Course, Module, Lesson, Content, Quiz, Question, Option

logger = logging.getLogger(__name__)

class PDFExtractionError(Exception):
    """Custom exception raised when PDF parsing fails."""
    pass


class PDFCourseExtractorService:
    """
    Handles PDF text extraction and uses Google Gemini 2.5 Flash 
    to auto-generate structured LMS courses matching your Django models.
    """

    @staticmethod
    def extract_text(pdf_file) -> str:
        """
        Memory-efficient text extraction for large files up to 100MB.
        """
        text = ""
        try:
            # pypdf reads from file pointers efficiently
            pdf_reader = pypdf.PdfReader(pdf_file)
            total_pages = len(pdf_reader.pages)
            
            logger.info(f"Processing large PDF with {total_pages} pages...")

            # Cap page processing to first 100 pages to avoid Gemini context overflow
            max_pages = min(total_pages, 100)

            for page_num in range(max_pages):
                page = pdf_reader.pages[page_num]
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
                    
        except Exception as e:
            logger.error(f"Error parsing large PDF: {str(e)}")
            raise ValueError("Could not extract readable text from the uploaded 100MB file.")

        return text

    @classmethod
    def generate_course_data(cls, raw_text: str, custom_title: str = None, generate_quiz: bool = True) -> dict:
        """
        Calls Gemini 3.6 Flash to generate structured course JSON.
        """
        client = genai.Client(api_key=settings.GEMINI_API_KEY)

        prompt = f"""
        You are an expert instructional designer.
        Analyze the following text extracted from a PDF document and structure it for an online learning management system.

        Requirements:
        1. Title: Create a concise course title (or use '{custom_title}' if provided).
        2. Description: A short HTML summary (<p>...</p>).
        3. Modules: Break the content into 3-5 logical modules.
        4. Lessons: Each module must contain 2-4 lessons.
        5. Contents: Each lesson must have reading material stored under 'text_content' formatted in HTML (<p>, <ul>, <strong>).
        {'6. Quiz: Generate 3-5 multiple choice questions testing key concepts.' if generate_quiz else ''}

        Return ONLY a valid JSON object matching this schema:
        {{
            "title": "Course Title",
            "description": "<p>Course description HTML</p>",
            "category": "beginner",
            "modules": [
                {{
                    "title": "Module Title",
                    "description": "<p>Module overview</p>",
                    "order": 1,
                    "lessons": [
                        {{
                            "title": "Lesson Title",
                            "description": "<p>Lesson overview</p>",
                            "order": 1,
                            "contents": [
                                {{
                                    "title": "Reading Title",
                                    "content_type": "text",
                                    "text_content": "<p>Detailed reading material formatted in HTML</p>",
                                    "order": 1
                                }}
                            ]
                        }}
                    ]
                }}
            ]
            {', "quiz": {"title": "Final Assessment", "pass_percentage": 70, "questions": [{"text": "Question?", "options": [{"text": "Option A", "is_correct": true}, {"text": "Option B", "is_correct": false}]}]}' if generate_quiz else ''}
        }}

        Source Document Text:
        {raw_text[:30000]}
        """

        try:
            response = client.models.generate_content(
                model='gemini-3.6-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )
            return json.loads(response.text)

        except Exception as e:
            logger.error(f"Gemini API generation error: {str(e)}")
            raise PDFExtractionError("AI generation service failed to process the document with Gemini.")

    @classmethod
    @transaction.atomic
    def build_course_from_pdf(cls, instructor, pdf_file, custom_title=None, generate_quiz=True) -> Course:
        """
        Extracts text, calls Gemini, and saves Course, Modules, Lessons, Content, and Quiz.
        """
        raw_text = cls.extract_text(pdf_file)
        if not raw_text.strip():
            raise ValueError("The uploaded PDF contains no readable text.")

        data = cls.generate_course_data(raw_text, custom_title=custom_title, generate_quiz=generate_quiz)

        # 1. Create Course
        course = Course.objects.create(
            title=data.get('title', custom_title or 'Imported PDF Course'),
            description=data.get('description', '<p>Generated course.</p>'),
            category=data.get('category', 'beginner'),
            instructor=instructor,
            is_published=False
        )

        # 2. Build Modules, Lessons, Content
        for m_idx, mod_data in enumerate(data.get('modules', []), start=1):
            module = Module.objects.create(
                course=course,
                title=mod_data.get('title', f'Module {m_idx}'),
                description=mod_data.get('description', ''),
                order=mod_data.get('order', m_idx)
            )

            for l_idx, les_data in enumerate(mod_data.get('lessons', []), start=1):
                lesson = Lesson.objects.create(
                    module=module,
                    title=les_data.get('title', f'Lesson {l_idx}'),
                    description=les_data.get('description', ''),
                    order=les_data.get('order', l_idx)
                )

                for c_idx, con_data in enumerate(les_data.get('contents', []), start=1):
                    Content.objects.create(
                        lesson=lesson,
                        title=con_data.get('title', f'Content {c_idx}'),
                        content_type=con_data.get('content_type', 'text'),
                        text_content=con_data.get('text_content', ''),
                        order=con_data.get('order', c_idx)
                    )

        # 3. Build Quiz
        quiz_data = data.get('quiz')
        if generate_quiz and quiz_data:
            quiz = Quiz.objects.create(
                course=course,
                title=quiz_data.get('title', f"{course.title} Final Assessment"),
                description=f"<p>Assessment quiz for {course.title}</p>",
                pass_percentage=quiz_data.get('pass_percentage', 70),
                created_by=instructor
            )

            for q_idx, q_info in enumerate(quiz_data.get('questions', []), start=1):
                question = Question.objects.create(
                    quiz=quiz,
                    text=q_info.get('text', ''),
                    order=q_idx
                )
                for opt_info in q_info.get('options', []):
                    Option.objects.create(
                        question=question,
                        text=opt_info.get('text', ''),
                        is_correct=opt_info.get('is_correct', False)
                    )

        return course
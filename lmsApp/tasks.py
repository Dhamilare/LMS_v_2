import logging
from celery import shared_task
from django.utils import timezone
from .models import CourseImportJob
from .services import PDFCourseExtractorService, PDFExtractionError, CourseGenerationError

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def process_course_import_job(self, job_id: int):
    try:
        job = CourseImportJob.objects.select_related("instructor").get(pk=job_id)
    except CourseImportJob.DoesNotExist:
        logger.error(f"CourseImportJob {job_id} not found.")
        return

    job.status = "extracting_text"
    job.started_at = timezone.now()
    job.save(update_fields=["status", "started_at"])

    def _on_progress(status: str, pct: int):
        CourseImportJob.objects.filter(pk=job_id).update(
            status=status, progress_percentage=pct
        )

    try:
        with job.pdf_file.open("rb") as f:
            course = PDFCourseExtractorService.build_course_from_pdf(
                instructor=job.instructor,
                pdf_file=f,
                custom_title=job.custom_title,
                generate_quiz=job.generate_quiz,
                min_questions=job.requested_min_questions,
                progress_callback=_on_progress,
            )

        job.course = course
        job.status = "completed"
        job.progress_percentage = 100
        job.completed_at = timezone.now()
        if hasattr(course, "quiz"):
            job.questions_generated = course.quiz.questions.count()
        job.save(update_fields=[
            "course", "status", "progress_percentage",
            "completed_at", "questions_generated",
        ])

    except PDFExtractionError as e:
        job.mark_failed(str(e))

    except CourseGenerationError as e:
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        job.mark_failed(f"Course generation failed after retries: {e}")

    except Exception as e:
        logger.exception(f"Unexpected error processing import job {job_id}")
        job.mark_failed(f"Unexpected error: {e}")
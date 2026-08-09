import logging
from celery import shared_task
from django.utils import timezone
from .models import *
from django.urls import reverse
from django.contrib.sites.models import Site
from django.conf import settings
from datetime import timedelta
from .utils import send_templated_email
from .services import *
from .models import ExternalTrainingResource
import requests

def _site_and_protocol():
    site = Site.objects.get_current()
    protocol = 'https' if not settings.DEBUG else 'http'
    return site.domain, protocol

logger = logging.getLogger(__name__)

LEARN_CATALOG_API_BASE = "https://learn.microsoft.com/api/catalog/"
LEARN_PLATFORM_LOCALE = "en-us"


def _metadata_names(items):
    """
    Extracts name attributes from lists of metadata dicts or strings.
    """
    if not items:
        return ""

    names = []
    for item in items:
        if isinstance(item, dict):
            name = item.get("name")
            if name:
                names.append(name)
        elif isinstance(item, str):
            names.append(item)

    return ", ".join(names)


def _fetch_learn_resources(
    products=None,
    roles=None,
    levels=None,
    subjects=None,
):
    """
    Generator that fetches pages from the public Microsoft Learn Catalog API.
    """
    params = {
        "locale": LEARN_PLATFORM_LOCALE,
    }

    if products:
        params["products"] = ",".join(products)
    if roles:
        params["roles"] = ",".join(roles)
    if levels:
        params["levels"] = ",".join(levels)
    if subjects:
        params["subjects"] = ",".join(subjects)

    url = LEARN_CATALOG_API_BASE

    while url:
        logger.info("Requesting Microsoft Learn catalog: %s", url)

        response = requests.get(
            url,
            params=params,
            timeout=60,
        )
        response.raise_for_status()

        data = response.json()
        yield data

        # Pagination support (params are set to None as nextLink contains the full query string)
        url = data.get("nextLink")
        params = None


def _sync_resource(item, now):
    """
    Creates or updates one Microsoft Learn resource in the database.
    """
    external_uid = item.get("uid") or item.get("id")
    
    if not external_uid:
        logger.warning("Skipping resource without an ID: %s", item)
        return None, False

    # Standard public API specifies type as 'module' or 'learningPath'
    resource_type = item.get("type")
    if resource_type and resource_type not in ("module", "learningPath"):
        return None, False

    title = item.get("title") or "Untitled"
    description = item.get("summary") or item.get("description") or ""

    levels = _metadata_names(item.get("levels", []))
    products = _metadata_names(item.get("products", []))

    duration = item.get("durationInMinutes") or item.get("duration_in_minutes")
    if duration is not None:
        try:
            duration = int(duration)
            if duration < 0:
                duration = None
        except (TypeError, ValueError):
            duration = None

    defaults = {
        "title": title[:255],
        "provider": "ms_learn",
        "source": "synced",
        "url": item.get("url") or "",
        "description": description[:2000],
        "duration_minutes": duration,
        "level": levels[:50] if levels else None,
        "product_area": products[:255] if products else None,
        "last_synced_at": now,
        "is_active": True,
    }

    resource, created = ExternalTrainingResource.objects.update_or_create(
        provider="ms_learn",
        external_uid=external_uid,
        source="synced",
        defaults=defaults,
    )

    return resource, created


@shared_task(
    bind=True,
    max_retries=3,
    autoretry_for=(requests.RequestException,),
    retry_backoff=True,
    retry_backoff_max=300,
)
def sync_microsoft_learn_catalog(
    self,
    products=None,
    roles=None,
    levels=None,
    subjects=None,
    updated_after=None,
):
    """
    Celery task to synchronize Microsoft Learn modules and learning paths.
    """
    logger.info("Starting Microsoft Learn catalog synchronization.")

    created = 0
    updated = 0
    processed = 0
    skipped = 0
    pages = 0

    now = timezone.now()

    for page in _fetch_learn_resources(
        products=products,
        roles=roles,
        levels=levels,
        subjects=subjects,
    ):
        pages += 1

        # The public API may return items under 'resources', or split between 'modules' and 'learningPaths'
        resources = page.get("resources")
        if resources is None:
            modules = page.get("modules", [])
            learning_paths = page.get("learningPaths", [])
            resources = modules + learning_paths

        logger.info(
            "Microsoft Learn page %s returned %s resources.",
            pages,
            len(resources),
        )

        for item in resources:
            resource, was_created = _sync_resource(item=item, now=now)

            if resource is None:
                skipped += 1
                continue

            processed += 1
            if was_created:
                created += 1
            else:
                updated += 1

    message = (
        "Microsoft Learn synchronization complete: "
        f"{created} created, "
        f"{updated} updated, "
        f"{processed} processed, "
        f"{skipped} skipped, "
        f"{pages} pages."
    )

    logger.info(message)
    return message


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


@shared_task(bind=True, max_retries=3)
def send_deadline_reminders(self):
    domain, protocol = _site_and_protocol()
    sent_7, sent_3 = 0, 0
 
    incomplete_enrollments = Enrollment.objects.filter(
        completed=False, due_date__isnull=False
    ).select_related('student', 'course')
 
    for enrollment in incomplete_enrollments:
        days_left = (enrollment.due_date.date() - timezone.now().date()).days
 
        if days_left == 7 and not enrollment.reminder_7_sent:
            send_templated_email(
                'emails/deadline_reminder_7day.html',
                f'Reminder: "{enrollment.course.title}" is due in 7 days',
                [enrollment.student.email],
                {
                    'student_name': enrollment.student.get_full_name() or enrollment.student.email,
                    'course_title': enrollment.course.title,
                    'due_date': enrollment.due_date,
                    'course_url': f"{protocol}://{domain}{enrollment.course.get_absolute_url()}",
                }
            )
            enrollment.reminder_7_sent = True
            enrollment.save(update_fields=['reminder_7_sent'])
            sent_7 += 1
 
        elif days_left == 3 and not enrollment.reminder_3_sent:
            send_templated_email(
                'emails/deadline_reminder_3day.html',
                f'Final reminder: "{enrollment.course.title}" is due in 3 days',
                [enrollment.student.email],
                {
                    'student_name': enrollment.student.get_full_name() or enrollment.student.email,
                    'course_title': enrollment.course.title,
                    'due_date': enrollment.due_date,
                    'course_url': f"{protocol}://{domain}{enrollment.course.get_absolute_url()}",
                }
            )
            enrollment.reminder_3_sent = True
            enrollment.save(update_fields=['reminder_3_sent'])
            sent_3 += 1
 
    return f"Sent {sent_7} 7-day reminders and {sent_3} 3-day reminders."


@shared_task(bind=True, max_retries=3)
def send_post_completion_followups(self):
    domain, protocol = _site_and_protocol()
    today = timezone.now().date()
    sent_2mo, sent_3mo = 0, 0
 
    completed_enrollments = Enrollment.objects.filter(
        completed=True, completed_at__isnull=False
    ).select_related('student', 'course')
 
    for enrollment in completed_enrollments:
        days_since_completion = (today - enrollment.completed_at.date()).days
 
        if 58 <= days_since_completion <= 62 and not enrollment.followup_2mo_sent:
            send_templated_email(
                'emails/post_completion_followup.html',
                f'Checking in — how has "{enrollment.course.title}" helped you?',
                [enrollment.student.email],
                {
                    'student_name': enrollment.student.get_full_name() or enrollment.student.email,
                    'course_title': enrollment.course.title,
                    'milestone': '2 months',
                    'protocol': protocol, 'domain': domain,
                }
            )
            enrollment.followup_2mo_sent = True
            enrollment.save(update_fields=['followup_2mo_sent'])
            sent_2mo += 1
 
        elif 88 <= days_since_completion <= 92 and not enrollment.followup_3mo_sent:
            send_templated_email(
                'emails/post_completion_followup.html',
                f'Checking in — how has "{enrollment.course.title}" helped you?',
                [enrollment.student.email],
                {
                    'student_name': enrollment.student.get_full_name() or enrollment.student.email,
                    'course_title': enrollment.course.title,
                    'milestone': '3 months',
                    'protocol': protocol, 'domain': domain,
                }
            )
            enrollment.followup_3mo_sent = True
            enrollment.save(update_fields=['followup_3mo_sent'])
            sent_3mo += 1
 
    return f"Sent {sent_2mo} 2-month and {sent_3mo} 3-month follow-ups."


@shared_task(bind=True, max_retries=3)
def send_monthly_platform_report(self):
    from django.db.models import Count, Q
 
    domain, protocol = _site_and_protocol()
    now = timezone.now()
    period_end = now.date()
    period_start = (now - timedelta(days=30)).date()
 
    new_enrollments = Enrollment.objects.filter(enrolled_at__date__gte=period_start).count()
    completions_this_period = Enrollment.objects.filter(completed_at__date__gte=period_start).count()
    certificates_issued = Certificate.objects.filter(issue_date__gte=period_start).count()
    total_active_students = User.objects.filter(is_student=True, is_active=True).count()
 
    course_stats = (
        Course.objects.annotate(
            enrollments_this_period=Count('enrollments', filter=Q(enrollments__enrolled_at__date__gte=period_start)),
        ).order_by('-enrollments_this_period')[:10]
    )
 
    recipients = list(
        User.objects.filter(is_active=True).filter(Q(is_hr=True) | Q(is_staff=True))
        .values_list('email', flat=True).distinct()
    )
    recipients = [e for e in recipients if e]
 
    if not recipients:
        return "No HR/Admin recipients found — report not sent."
 
    send_templated_email(
        'emails/monthly_platform_report.html',
        f"Platform Usage Report — {period_start.strftime('%B %Y')}",
        recipients,
        {
            'period_start': period_start,
            'period_end': period_end,
            'new_enrollments': new_enrollments,
            'completions_this_period': completions_this_period,
            'certificates_issued': certificates_issued,
            'total_active_students': total_active_students,
            'top_courses': course_stats,
            'dashboard_url': f"{protocol}://{domain}{reverse('audit_logs')}",
        }
    )
 
    ReportLog.objects.create(
        report_type='monthly_usage',
        recipient_emails=', '.join(recipients),
        period_start=period_start,
        period_end=period_end,
    )
 
    return f"Monthly report sent to {len(recipients)} recipients."


@shared_task(bind=True, max_retries=3)
def send_bulk_assignment_emails(self, course_id, student_ids, assigner_id, due_date_iso):
    from django.utils.dateparse import parse_datetime
 
    domain, protocol = _site_and_protocol()
    course = Course.objects.get(id=course_id)
    assigner = User.objects.get(id=assigner_id)
    due_date = parse_datetime(due_date_iso)
    students = User.objects.filter(id__in=student_ids)
 
    for student in students:
        send_templated_email(
            'emails/bulk_assignment_notification.html',
            f'You have been assigned: {course.title}',
            [student.email],
            {
                'student_name': student.get_full_name() or student.email,
                'course_title': course.title,
                'assigned_by': assigner.get_full_name() or assigner.email,
                'due_date': due_date,
                'course_url': f"{protocol}://{domain}{course.get_absolute_url()}",
            }
        )
 
    return f"Sent {students.count()} bulk-assignment emails for course '{course.title}'."


@shared_task(bind=True, max_retries=3)
def notify_admin_instructor_training_completed(self, training_id):
    domain, protocol = _site_and_protocol()
    training = InstructorTraining.objects.select_related('instructor', 'course').get(id=training_id)
 
    admin_emails = list(
        User.objects.filter(is_staff=True, is_active=True).values_list('email', flat=True)
    )
    admin_emails = [e for e in admin_emails if e]
    if not admin_emails:
        return "No admin recipients found."
 
    context = {
        'instructor_name': training.instructor.get_full_name() or training.instructor.email,
        'training_title': training.training_title,
        'completed_at': training.completed_at,
        'completion_note': training.completion_note,
        'review_url': f"{protocol}://{domain}{reverse('admin_training_review')}",
    }
    attachments = []
    if training.proof_file:
        with training.proof_file.open('rb') as f:
            attachments.append((training.proof_file.name.split('/')[-1], f.read(), 'application/octet-stream'))
 
    send_templated_email(
        'emails/instructor_training_completed_notification.html',
        f"Training Completed: {training.instructor.get_full_name()} — {training.training_title}",
        admin_emails,
        context,
        attachments=attachments or None,
    )
    return f"Notified {len(admin_emails)} admin(s) of completed training #{training_id}."


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def process_external_resource_import_job(self, job_id: int):
    try:
        job = (
            ExternalResourceImportJob.objects
            .select_related("instructor")
            .prefetch_related("external_resources")
            .get(pk=job_id)
        )
    except ExternalResourceImportJob.DoesNotExist:
        logger.error(f"ExternalResourceImportJob {job_id} not found.")
        return
 
    job.status = "generating_outline"
    job.started_at = timezone.now()
    job.save(update_fields=["status", "started_at"])
 
    def _on_progress(status: str, pct: int):
        ExternalResourceImportJob.objects.filter(pk=job_id).update(status=status, progress_percentage=pct)
 
    resources = list(job.external_resources.all())
    if not resources:
        job.mark_failed("No external resources were attached to this import job.")
        return
 
    try:
        if len(resources) == 1:
            course = ExternalResourceCourseGeneratorService.build_course_from_single_resource(
                instructor=job.instructor,
                resource=resources[0],
                custom_title=job.custom_title,
                generate_quiz=job.generate_quiz,
                min_questions=job.requested_min_questions,
                progress_callback=_on_progress,
            )
        else:
            course = ExternalResourceCourseGeneratorService.build_course_from_resources(
                instructor=job.instructor,
                resources=resources,
                custom_title=job.custom_title,
                generate_quiz=job.generate_quiz,
                generate_module_quizzes=job.generate_module_quizzes,
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
            "course", "status", "progress_percentage", "completed_at", "questions_generated",
        ])
 
    except CourseGenerationError as e:
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        job.mark_failed(f"Course generation failed after retries: {e}")
 
    except Exception as e:
        logger.exception(f"Unexpected error processing external resource import job {job_id}")
        job.mark_failed(f"Unexpected error: {e}")
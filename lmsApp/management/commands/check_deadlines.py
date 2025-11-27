from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta
from django.conf import settings
from django.urls import reverse
from lmsApp.utils import *
from lmsApp.models import Enrollment

class Command(BaseCommand):
    help = 'Checks for course enrollments with a deadline approaching in 3 days and sends reminder emails.'

    def handle(self, *args, **options):
        reminder_date_target = timezone.now().date() + timedelta(days=3)
        self.stdout.write(f"Starting deadline check for date: {reminder_date_target}")

        enrollments_to_remind = Enrollment.objects.select_related(
            'student', 'course'
        ).filter(
            Q(due_date__date=reminder_date_target),
            completed=False
        )

        if not enrollments_to_remind.exists():
            self.stdout.write(self.style.SUCCESS("No students require a deadline reminder today."))
            return

        sent_count = 0

        for enrollment in enrollments_to_remind:
            student = enrollment.student
            course = enrollment.course

            # ---- Calculate progress ----
            total_content = sum(
                len(lesson.contents.all())
                for module in course.modules.all()
                for lesson in module.lessons.all()
            )

            completed_content = student.content_progress.filter(
                content__lesson__module__course=course,
                completed=True
            ).count()

            progress_percentage = round((completed_content / total_content) * 100, 0) if total_content else 0

            # ---- Email context ----
            context = {
                'student_name': student.get_full_name() or student.email,
                'course_title': course.title,
                'due_date': enrollment.due_date.strftime("%B %d, %Y"),
                'progress_percentage': progress_percentage,
                'course_url': f"{settings.BASE_URL}{reverse('course_detail', args=[course.slug])}",
            }

            subject = f"URGENT: 3-Day Deadline for Course: {course.title}"

            try:
                success = send_templated_email(
                    template_name='emails/deadline_reminder.html',
                    subject=subject,
                    recipient_list=[student.email],
                    context=context,
                )

                if success:
                    sent_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f"Reminder sent to {student.email} for {course.title}")
                    )
                else:
                    self.stderr.write(
                        self.style.ERROR(f"Failed to send to {student.email}")
                    )

            except Exception as e:
                self.stderr.write(
                    self.style.ERROR(f"Error sending email to {student.email}: {e}")
                )

        self.stdout.write(self.style.SUCCESS(f"Finished sending {sent_count} deadline reminders."))

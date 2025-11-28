from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import *
from django.db.models import Sum
from .utils import *

@receiver([post_save, post_delete], sender=Content)
def update_course_duration(sender, instance, **kwargs):
    try:
        course = instance.lesson.module.course
        total_duration = Content.objects.filter(
            lesson__module__course=course
        ).aggregate(total_duration=Sum('duration'))['total_duration'] or 0

        course.duration = total_duration
        course.save(update_fields=['duration'])

    except Exception:
        pass


@receiver(post_save, sender=Course)
def notify_students_on_course_update(sender, instance, created, **kwargs):
    update_fields = kwargs.get('update_fields')

    if update_fields and set(update_fields) == {'duration'}:
        return

    if not instance.is_published:
        return
    
    action_type = "newly published" if created else "updated"

    course_tags = list(instance.tags.values_list('name', flat=True))
    if not course_tags:
        return

    matching_students = User.objects.filter(
        is_student=True,
        is_active=True,
        department__in=course_tags
    ).distinct()

    if matching_students.exists():
        send_course_notification(instance, matching_students, action_type)

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import *
from django.db.models import Sum
from .utils import *

@receiver([post_save, post_delete], sender=Content)
def update_course_duration(sender, instance, **kwargs):
    """
    Signal handler to update the total duration of a course whenever a
    Content item is saved or deleted.
    """
    try:
        course = instance.lesson.module.course
        total_duration = Content.objects.filter(
            lesson__module__course=course
        ).aggregate(total_duration=Sum('duration'))['total_duration'] or 0
        
        course.duration = total_duration
        course.save(update_fields=['duration'])

    except (Course.DoesNotExist, Lesson.DoesNotExist, Module.DoesNotExist):
        pass


@receiver(post_save, sender=Course)
def notify_students_on_course_update(sender, instance, created, **kwargs):
    """
    Sends personalized email notification to students whose department tags match 
    the saved course's tags, upon initial publish or major update.
    """
    # Only proceed if the course is published
    if not instance.is_published:
        return
    
    # Determine the type of notification
    action_type = "newly published" if created else "updated"
    
    # 1. Get the list of tag names associated with the course
    course_tags = list(instance.tags.values_list('name', flat=True))

    if not course_tags:
        # If the course has no tags, we cannot personalize the notification
        print(f"Course {instance.title} saved, but has no tags for filtering.")
        return

    matching_students = User.objects.filter(
        is_student=True,
        is_active=True,
        department__in=course_tags
    ).distinct()

    if matching_students.exists():
        send_course_notification(instance, matching_students, action_type)

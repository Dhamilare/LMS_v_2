from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Content, Course, Module, Lesson
from django.db.models import Sum

@receiver([post_save, post_delete], sender=Content)
def update_course_duration(sender, instance, **kwargs):
    """
    Signal handler to update the total duration of a course whenever a
    Content item is saved or deleted.
    """
    try:
        # Get the course associated with the content instance
        course = instance.lesson.module.course
        
        # Calculate the sum of all content durations for that course
        total_duration = Content.objects.filter(
            lesson__module__course=course
        ).aggregate(total_duration=Sum('duration'))['total_duration'] or 0
        
        # Update the course's duration field and save it
        course.duration = total_duration
        course.save(update_fields=['duration'])

    except (Course.DoesNotExist, Lesson.DoesNotExist, Module.DoesNotExist):
        # Handle cases where the related objects might not exist
        # This can happen during cascading deletes, etc.
        pass


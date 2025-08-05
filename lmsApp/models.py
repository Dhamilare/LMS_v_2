from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
import uuid
from django.urls import reverse

class User(AbstractUser):
    """
    Custom User model extending Django's AbstractUser.
    Adds fields to differentiate between instructors and students.
    """
    is_instructor = models.BooleanField(default=False)
    is_student = models.BooleanField(default=True)

    def __str__(self):
        return self.username

class Course(models.Model):
    """
    Represents a course in the LMS.
    """
    title = models.CharField(max_length=200)
    description = models.TextField()
    instructor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='courses_taught', limit_choices_to={'is_instructor': True})
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    thumbnail = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text="URL for the course thumbnail image."
    )
    slug = models.SlugField(unique=True, max_length=255, blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            unique_slug = base_slug
            num = 1
            while Course.objects.filter(slug=unique_slug).exists():
                unique_slug = f"{base_slug}-{num}"
                num += 1
            self.slug = unique_slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['-created_at']

    def get_absolute_url(self):
        return reverse('course_detail', kwargs={'slug': self.slug})

class Module(models.Model):
    """
    Represents a module or chapter within a course.
    """
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='modules')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    order = models.PositiveIntegerField(default=0, help_text="Order of the module within the course.")

    def __str__(self):
        return f"{self.course.title} - {self.title}"

    class Meta:
        ordering = ['order']
        unique_together = ('course', 'order')

class Lesson(models.Model):
    """
    Represents an individual lesson within a module.
    """
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='lessons')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    order = models.PositiveIntegerField(default=0, help_text="Order of the lesson within the module.")

    def __str__(self):
        return f"{self.module.course.title} - {self.module.title} - {self.title}"

    class Meta:
        ordering = ['order']
        unique_together = ('module', 'order')

class Content(models.Model):
    """
    Represents various types of content within a lesson.
    """
    CONTENT_TYPES = (
        ('video', 'Video'),
        ('pdf', 'PDF Document'),
        ('text', 'Text/Notes'),
    )
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='contents')
    title = models.CharField(max_length=200)
    content_type = models.CharField(max_length=20, choices=CONTENT_TYPES)
    file = models.FileField(upload_to='lms_content/', blank=True, null=True, help_text="Upload video, PDF, or other files.")
    text_content = models.TextField(blank=True, null=True, help_text="For text-based content (e.g., notes).")
    video_url = models.URLField(max_length=500, blank=True, null=True, help_text="URL for external video (e.g., YouTube, Vimeo).")
    order = models.PositiveIntegerField(default=0, help_text="Order of the content within the lesson.")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.lesson.title} - {self.title} ({self.get_content_type_display()})"

    class Meta:
        ordering = ['order']
        unique_together = ('lesson', 'order')

class Enrollment(models.Model):
    """
    Represents a student's enrollment in a course.
    """
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='enrollments', limit_choices_to={'is_student': True})
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    enrolled_at = models.DateTimeField(auto_now_add=True)
    completed = models.BooleanField(default=False)

    class Meta:
        unique_together = ('student', 'course')
        ordering = ['-enrolled_at']

    def __str__(self):
        return f"{self.student.username} enrolled in {self.course.title}"

class StudentContentProgress(models.Model):
    """
    Tracks a student's progress on individual content items within a course.
    """
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='content_progress', limit_choices_to={'is_student': True})
    content = models.ForeignKey(Content, on_delete=models.CASCADE, related_name='student_progress')
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('student', 'content')
        verbose_name = "Student Content Progress"
        verbose_name_plural = "Student Content Progress"

    def save(self, *args, **kwargs):
        if self.completed and not self.completed_at:
            self.completed_at = timezone.now()
        elif not self.completed and self.completed_at:
            self.completed_at = None
        super().save(*args, **kwargs)

    def __str__(self):
        status = "Completed" if self.completed else "Incomplete"
        return f"{self.student.username} - {self.content.title} ({status})"


class Quiz(models.Model):
    """
    Represents a quiz. Can be linked to a Content object of type 'quiz'.
    """
    lesson = models.OneToOneField(Lesson, on_delete=models.CASCADE, related_name='quiz', null=True, blank=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    duration_minutes = models.PositiveIntegerField(default=0)
    pass_percentage = models.PositiveIntegerField(default=70)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name_plural = "Quizzes"

class Question(models.Model):
    """
    Represents a question within a quiz.
    """
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    order = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"Q{self.order}: {self.text[:50]}..."

    class Meta:
        ordering = ['order']
        unique_together = ('quiz', 'order')

class Option(models.Model):
    """
    Represents an answer option for a multiple-choice question.
    """
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='options')
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.text} ({'Correct' if self.is_correct else 'Incorrect'})"

    class Meta:
        unique_together = ('question', 'text')

class StudentQuizAttempt(models.Model):
    """
    Tracks a student's attempt on a specific quiz.
    """
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quiz_attempts', limit_choices_to={'is_student': True})
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    passed = models.BooleanField(default=False)
    attempt_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        status = "Passed" if self.passed else "Failed"
        return f"{self.student.username} - {self.quiz.title} ({self.score or 'N/A'}% - {status})"

    class Meta:
        ordering = ['-attempt_date']

class StudentAnswer(models.Model):
    """
    Stores a student's chosen answer for a specific question within a quiz attempt.
    """
    attempt = models.ForeignKey(StudentQuizAttempt, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='student_answers')
    chosen_option = models.ForeignKey(Option, on_delete=models.CASCADE, null=True, blank=True, related_name='chosen_by_students')

    def __str__(self):
        return f"{self.attempt.student.username}'s answer for {self.question.text[:30]}..."

    class Meta:
        unique_together = ('attempt', 'question')


class Certificate(models.Model):
    """
    Represents a certificate of completion issued to a student for a course.
    """
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='certificates', limit_choices_to={'is_student': True})
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='certificates')
    issue_date = models.DateField(auto_now_add=True)
    certificate_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    pdf_file = models.FileField(upload_to='certificates/', blank=True, null=True)

    class Meta:
        unique_together = ('student', 'course')
        ordering = ['-issue_date']

    def __str__(self):
        return f"Certificate for {self.student.username} - {self.course.title} (Issued: {self.issue_date})"
    
    def get_absolute_url(self):
        return reverse('view_certificate', kwargs={'certificate_id': self.certificate_id})

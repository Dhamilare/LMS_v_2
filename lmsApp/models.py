from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
import uuid
from django.urls import reverse
from django.db.models import Sum, F, Count

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

    def is_completed_by_student(self, user):
        """
        Checks if all lessons within this module are completed by the given student.
        A module is completed if all its lessons are completed.
        """
        if not user.is_authenticated or not user.is_student:
            return False
        
        lessons_in_module = self.lessons.all()
        if not lessons_in_module.exists():
            return True

        # Check if ALL lessons are completed by the student
        for lesson in lessons_in_module:
            if not lesson.is_completed_by_student(user):
                return False
        return True

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

    def is_completed_by_student(self, user):
        """
        Checks if all content items within this lesson are completed by the given student.
        This does NOT include course-level quizzes.
        """
        if not user.is_authenticated or not user.is_student:
            return False

        # Get all content items in this lesson (quizzes are now course-level)
        all_contents_in_lesson = self.contents.all()
        
        if not all_contents_in_lesson.exists():
            return True # A lesson with no content is considered completed for progression

        # Check if ALL content items are completed by the student
        for content_item in all_contents_in_lesson:
            if not content_item.is_completed_by_student(user):
                return False
        
        return True # All content are completed

class Content(models.Model):
    """
    Represents various types of content within a lesson.
    """
    CONTENT_TYPES = (
        ('video', 'Video'),
        ('pdf', 'PDF Document'),
        ('text', 'Text/Notes'),
        ('slide', 'Slide Presentation'),
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

    def is_completed_by_student(self, user):
        """
        Checks if this specific content item is completed by the given student.
        """
        if not user.is_authenticated or not user.is_student:
            return False
        
        return StudentContentProgress.objects.filter(
            student=user,
            content=self,
            completed=True
        ).exists()

class Enrollment(models.Model):
    """
    Represents a student's enrollment in a course.
    """
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='enrollments', limit_choices_to={'is_student': True})
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    enrolled_at = models.DateTimeField(auto_now_add=True)
    completed = models.BooleanField(default=False) # This will be managed by _sync_completion_status
    completed_at = models.DateTimeField(null=True, blank=True) # This will be managed by _sync_completion_status

    class Meta:
        unique_together = ('student', 'course')
        ordering = ['-enrolled_at']

    def __str__(self):
        return f"{self.student.username} enrolled in {self.course.title}"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    @property
    def progress_percentage(self):
        """Calculates the percentage of completed content (all non-quiz content) for this enrollment."""
        # This property might become less relevant for overall course completion
        # if completion is strictly module-by-module + final quiz.
        # It still serves as a general indicator of content consumption.

        # Get all non-quiz content items for the course
        total_contents = Content.objects.filter(
            lesson__module__course=self.course
        ).count() # Now 'quiz' content_type is removed from Content model

        if total_contents == 0:
            return 0

        # Count completed content items for this student in this course
        completed_contents = StudentContentProgress.objects.filter(
            student=self.student,
            content__lesson__module__course=self.course,
            completed=True
        ).count()

        return round((completed_contents / total_contents) * 100)

    @property
    def is_content_completed(self):
        """Returns True if all modules and their contained lessons/content are completed."""
        all_modules = self.course.modules.all()
        if not all_modules.exists():
            return False # A course with no modules cannot be content-completed

        for module in all_modules:
            if not module.is_completed_by_student(self.student):
                return False
        return True

    @property
    def is_quiz_passed(self):
        """
        Checks if the student has a passing attempt for the course's associated quiz.
        """
        course_quiz = getattr(self.course, 'quiz', None) # Access the related quiz object directly from course

        if not course_quiz:
            return True # No quiz for this course, so consider it passed by default for completion criteria

        # Check for any passing attempt by this student for this specific quiz
        return StudentQuizAttempt.objects.filter(
            student=self.student,
            quiz=course_quiz,
            passed=True
        ).exists()

    def _sync_completion_status(self):
        """
        Synchronizes the 'completed' status of the enrollment based on
        content completion (all modules/lessons) and course-level quiz passing status.
        This method should be called whenever content progress or quiz attempts change.
        """
        should_be_completed = self.is_content_completed and self.is_quiz_passed

        if should_be_completed and not self.completed:
            self.completed = True
            self.completed_at = timezone.now()
            self.save(update_fields=['completed', 'completed_at'])
        elif not should_be_completed and self.completed:
            self.completed = False
            self.completed_at = None
            self.save(update_fields=['completed', 'completed_at'])

    @property
    def has_certificate(self):
        """Checks if a certificate has been issued for this enrollment."""
        return Certificate.objects.filter(student=self.student, course=self.course).exists()

    @property
    def certificate_obj(self):
        """Returns the certificate object if it exists, otherwise None."""
        return Certificate.objects.filter(student=self.student, course=self.course).first()

    @property
    def can_claim_certificate(self):
        """Checks if the student can claim a certificate for this enrollment."""
        # Student can claim if enrollment is completed (meaning content + quiz passed)
        # AND no certificate has been issued yet.
        return self.completed and not self.has_certificate


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
        # Set completed_at for this specific content progress entry
        if self.completed and not self.completed_at:
            self.completed_at = timezone.now()
        elif not self.completed and self.completed_at:
            self.completed_at = None
        
        super().save(*args, **kwargs) # Save the content progress first

        # After saving content progress, trigger the enrollment completion status sync
        enrollment = Enrollment.objects.filter(
            student=self.student,
            course=self.content.lesson.module.course
        ).first()

        if enrollment:
            enrollment._sync_completion_status()


    def __str__(self):
        status = "Completed" if self.completed else "Incomplete"
        return f"{self.student.username} - {self.content.title} ({status})"


class Quiz(models.Model):
    """
    Represents a quiz, now linked directly to a Course.
    """
    course = models.OneToOneField(Course, on_delete=models.CASCADE, related_name='quiz', null=True, blank=True,
                                  help_text="The course this quiz is the main assessment for.")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    pass_percentage = models.PositiveIntegerField(default=70)
    max_attempts = models.PositiveIntegerField(default=3, help_text="Maximum number of attempts allowed for this quiz.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='created_quizzes',
        help_text="The instructor who created this quiz."
    )

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
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name='quiz_attempts_for_enrollment', null=True, blank=True)
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    passed = models.BooleanField(default=False)
    attempt_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-attempt_date']

    def save(self, *args, **kwargs):
        # Calculate score and set 'passed' status before saving
        if self.score is not None and self.quiz.pass_percentage is not None:
            self.passed = self.score >= self.quiz.pass_percentage
        
        super().save(*args, **kwargs) # Save the attempt first

        # After saving the attempt, trigger the enrollment completion status sync
        # Ensure 'enrollment' is set, if not, try to find it via quiz -> course
        if not self.enrollment and self.quiz.course:
            self.enrollment = Enrollment.objects.filter(
                student=self.student,
                course=self.quiz.course
            ).first()
            if self.enrollment:
                # If enrollment was just found and assigned, save again to persist the FK
                super().save(update_fields=['enrollment']) # Save the FK link

        if self.enrollment:
            self.enrollment._sync_completion_status()


    def __str__(self):
        status = "Passed" if self.passed else "Failed"
        return f"{self.student.username} - {self.quiz.title} ({self.score or 'N/A'}% - {status})"


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

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
import uuid
from django.urls import reverse
from django.db.models import Sum
from django.core.validators import MinValueValidator, MaxValueValidator
import random
import string
from django_ckeditor_5.fields import CKEditor5Field
from django.utils.translation import gettext_lazy as _
from django.db.models import Q
from datetime import timedelta
from django.conf import settings
from django.core.exceptions import ValidationError



class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError(_('The Email must be set'))
        
        email = self.normalize_email(email)
        username = extra_fields.pop('username', email)

        user = self.model(
            email=email,
            username=username,
            **extra_fields 
        )

        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()

        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, first_name, last_name, **extra_fields):
        """
        Create and save a SuperUser with the given email, password, first_name, and last_name.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))
        extra_fields['first_name'] = first_name
        extra_fields['last_name'] = last_name

        return self.create_user(email, password, **extra_fields)



class User(AbstractUser):
    """
    Custom User model extending Django's AbstractUser.
    Uses email as the primary identifier.
    """
    is_instructor = models.BooleanField(default=False)
    is_student = models.BooleanField(default=True)
    is_hr = models.BooleanField(default=False)
    username = models.CharField(
        _('username'),
        max_length=150,
        blank=True, 
        null=True,
        help_text=_('Required for staff/admin, optional for others. Can be same as email.'),
    )
    department = models.CharField(max_length=100, blank=True, null=True)
    
    email = models.EmailField(_('email address'), unique=True)
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name'] 

    objects = UserManager()

    def __str__(self):
        full_name = self.get_full_name()
        return full_name if full_name else self.email
    
    def save(self, *args, **kwargs):
        if not self.username:
            self.username = self.email
        super().save(*args, **kwargs)

    def promote_to_superuser(self):
        """Promote user to superuser and strip instructor/student roles."""
        self.is_staff = True
        self.is_superuser = True
        self.is_student = False
        self.is_instructor = False
        self.is_hr = False
        self.save()
    

class Course(models.Model):
    
    CATEGORY_CHOICES = [
        ('beginner', 'Beginner'),
        ('expert', 'Expert'),
        ('professional', 'Professional'),
    ]

    title = models.CharField(max_length=200)
    description = CKEditor5Field(config_name='default')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='beginner')
    instructor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='courses_taught', limit_choices_to={'is_instructor': True})
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    thumbnail = models.ImageField(
        upload_to='course_thumbnails/',
        blank=True,
        null=True,
        help_text="Upload a square image file for the course thumbnail."
    )
    duration = models.PositiveIntegerField(
        default=0, 
        help_text="Total estimated duration of the course in minutes."
    )
    default_duration_days = models.IntegerField(
        default=30, 
        help_text="Default days allowed for a student to complete this course."
    )
    tags = models.ManyToManyField(Tag, related_name='courses', blank=True, help_text="Select relevant departments or skills for this course.")
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
    
    def update_duration(self):
        """
        Recalculates and updates the total course duration.
        """
        total_duration = self.modules.aggregate(
            total_duration=Sum('lessons__contents__duration')
        )['total_duration'] or 0

        self.duration = total_duration
        self.save(update_fields=['duration'])

class Module(models.Model):
    """
    Represents a module or chapter within a course.
    """
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='modules')
    title = models.CharField(max_length=200)
    description = CKEditor5Field(config_name='default')
    order = models.PositiveIntegerField(default=0, help_text="Order of the module within the course.")

    def __str__(self):
        return f"{self.course.title} - {self.title}"

    class Meta:
        ordering = ['order']
        # unique_together = ('course', 'order')

    def is_completed_by_student(self, user):
        """
        Checks if all lessons within this module are completed by the given student.
        A module is completed if all its lessons are completed.
        """
        if not user.is_authenticated or not user.is_student:
            return False

        if hasattr(self, 'quiz') and self.quiz is not None:
            from .models import StudentQuizAttempt  # avoid circular import issues if split into files
            has_passed = StudentQuizAttempt.objects.filter(
                student=user, quiz=self.quiz, passed=True
            ).exists()
            if not has_passed:
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
    description = CKEditor5Field(config_name='default')
    order = models.PositiveIntegerField(default=0, help_text="Order of the lesson within the module.")

    def __str__(self):
        return f"{self.module.course.title} - {self.module.title} - {self.title}"

    class Meta:
        ordering = ['order']
        # unique_together = ('module', 'order')

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
        
        return True 

class Content(models.Model):
    """
    Represents various types of content within a lesson.
    """
    CONTENT_TYPES = (
        ('video', 'Video'),
        ('pdf', 'PDF Document'),
        ('text', 'Text/Notes'),
        ('slide', 'Slide Presentation'),
        ('image', 'Image/Diagram (extracted)'),
        ('diagram', 'Generated Diagram (Mermaid)'),
    )
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='contents')
    title = models.CharField(max_length=200)
    content_type = models.CharField(max_length=20, choices=CONTENT_TYPES)
    file = models.FileField(upload_to='lms_content/', blank=True, null=True, help_text="Upload video, PDF, or other files.")
    text_content = models.TextField(blank=True, null=True, help_text="For text-based content (e.g., notes).")
    video_url = models.URLField(max_length=500, blank=True, null=True, help_text="URL for external video (e.g., YouTube, Vimeo).")
    image = models.ImageField(
        upload_to='lms_content_images/',
        blank=True, null=True,
        help_text="Image extracted directly from the source PDF page."
    )
    diagram_code = models.TextField(
        blank=True, null=True,
        help_text=(
            "Mermaid.js syntax for a generated conceptual diagram "
            "(flowchart, sequence, hierarchy). Rendered client-side "
            "with mermaid.js; not a raster image."
        )
    )
    source_page_number = models.PositiveIntegerField(
        blank=True, null=True,
        help_text="Page in the source PDF this content was derived from, "
            "for traceability back to the original document."
    )
    order = models.PositiveIntegerField(default=0, help_text="Order of the content within the lesson.")
    created_at = models.DateTimeField(auto_now_add=True)
    duration = models.PositiveIntegerField(
        default=0, 
        help_text="Total estimated duration of the content in minutes."
    )

    def __str__(self):
        return f"{self.lesson.title} - {self.title} ({self.get_content_type_display()})"

    class Meta:
        ordering = ['order']
        # unique_together = ('lesson', 'order')

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
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.lesson and self.lesson.module and self.lesson.module.course:
            self.lesson.module.course.update_duration()

    def delete(self, *args, **kwargs):
        course = self.lesson.module.course
        super().delete(*args, **kwargs)
        course.update_duration()

class Enrollment(models.Model):
    """
    Represents a student's enrollment in a course.
    """
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='enrollments', limit_choices_to={'is_student': True})
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    enrolled_at = models.DateTimeField(auto_now_add=True)
    completed = models.BooleanField(default=False) 
    completed_at = models.DateTimeField(null=True, blank=True)
    has_completed_survey = models.BooleanField(default=False)
    assigned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_enrollments',
        limit_choices_to=~Q(is_student=True)
    )
    due_date = models.DateTimeField(null=True, blank=True)
    reminder_7_sent = models.BooleanField(default=False)
    reminder_3_sent = models.BooleanField(default=False)
    followup_2mo_sent = models.BooleanField(default=False)
    followup_3mo_sent = models.BooleanField(default=False)

    ASSIGNMENT_REASON_CHOICES = [
        ('self', 'Self-Enrolled'),
        ('manual', 'Manually Assigned'),
        ('bulk_department', 'Bulk Assigned by Department'),
    ]
    assignment_reason = models.CharField(
        max_length=20, choices=ASSIGNMENT_REASON_CHOICES, default='self'
    )

    class Meta:
        unique_together = ('student', 'course')
        ordering = ['-enrolled_at']

    def __str__(self):
        student_name = self.student.get_full_name() or self.student.email
        return f"{student_name} enrolled in {self.course.title}"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    @property
    def days_until_due(self):
        if not self.due_date:
            return None
        return (self.due_date.date() - timezone.now().date()).days

    @property
    def progress_percentage(self):
        """
        Calculates overall progress percentage.
        If course has a quiz: content = 80%, quiz = 20%.
        If no quiz: content = 100%.
        """
        total_contents = Content.objects.filter(
            lesson__module__course=self.course
        ).count()

        if total_contents == 0:
            content_percentage = 0
        else:
            completed_contents = StudentContentProgress.objects.filter(
                student=self.student,
                content__lesson__module__course=self.course,
                completed=True
            ).count()
            content_percentage = (completed_contents / total_contents) * 100

        if hasattr(self.course, 'quiz'):
            has_passed_quiz = StudentQuizAttempt.objects.filter(
                student=self.student,
                quiz=self.course.quiz,
                passed=True
            ).exists()
            quiz_percentage = 100 if has_passed_quiz else 0
            return round((content_percentage * 0.8) + (quiz_percentage * 0.2))

        return round(content_percentage)

    @property
    def is_content_completed(self):
        """Returns True if all modules and their contained lessons/content are completed."""
        all_modules = self.course.modules.all()
        if not all_modules.exists():
            return True

        for module in all_modules:
            if not module.is_completed_by_student(self.student):
                return False
        return True

    @property
    def is_quiz_passed(self):
        """
        Checks if the student has a passing attempt for the course's associated quiz.
        """
        course_quiz = getattr(self.course, 'quiz', None) 

        if not course_quiz:
            return True # No quiz for this course, so consider it passed

        return StudentQuizAttempt.objects.filter(
            student=self.student,
            quiz=course_quiz,
            passed=True
        ).exists()

    def _sync_completion_status(self):
        """
        Synchronizes the 'completed' status of the enrollment based on
        content completion (all modules/lessons) and course-level quiz passing status.
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

    def save(self, *args, **kwargs):
        if not self.pk and not self.due_date:
            self.due_date = timezone.now() + timedelta(days=30)
        super().save(*args, **kwargs)

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
        return self.completed and self.has_completed_survey and not self.has_certificate


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

        enrollment = Enrollment.objects.filter(
            student=self.student,
            course=self.content.lesson.module.course
        ).first()

        if enrollment:
            was_completed = enrollment.completed
            enrollment._sync_completion_status()

            if not was_completed and enrollment.completed:
                pass

    def __str__(self):
        status = "Completed" if self.completed else "Incomplete"
        student_name = self.student.get_full_name() or self.student.email
        return f"{student_name} - {self.content.title} ({status})"


class Quiz(models.Model):
    """
    Represents a quiz, now linked directly to a Course.
    """
    QUIZ_TYPE_CHOICES = [
        ('final', 'Final Course Assessment'),
        ('module_check', 'Module Knowledge Check'),
    ]
    quiz_type = models.CharField(max_length=20, choices=QUIZ_TYPE_CHOICES, default='final')
    course = models.OneToOneField(Course, on_delete=models.CASCADE, related_name='quiz', null=True, blank=True, help_text="Set only when quiz_type='final'. The course this quiz is the main assessment for.")
    title = models.CharField(max_length=255)
    allow_multiple_correct = models.BooleanField(default=False)
    description = CKEditor5Field(config_name='default')
    pass_percentage = models.PositiveIntegerField(default=70)
    max_attempts = models.PositiveIntegerField(default=3, help_text="Maximum number of attempts allowed for this quiz.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='created_quizzes',
        help_text="The instructor who created this quiz."
    )
    module = models.OneToOneField(
        Module, on_delete=models.CASCADE, related_name='quiz', null=True, blank=True,
        help_text="Set only when quiz_type='module_check'. The module this knowledge check belongs to."
    )

    def clean(self):
        super().clean()
        if self.quiz_type == 'final' and not self.course:
            raise ValidationError("A final assessment quiz must be linked to a course.")
        if self.quiz_type == 'module_check' and not self.module:
            raise ValidationError("A module knowledge check must be linked to a module.")
        if self.course and self.module:
            raise ValidationError("A quiz cannot be linked to both a course and a module.")
 
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
 
    @property
    def owning_course(self):
        '''Returns the Course regardless of whether this is a final or module-level quiz.'''
        if self.course:
            return self.course
        if self.module:
            return self.module.course
        return None

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
    is_multi_select = models.BooleanField(default=False, help_text="Check if this question allows multiple correct answers.")
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
        if self.score is not None and self.quiz.pass_percentage is not None:
            self.passed = self.score >= self.quiz.pass_percentage
 
        super().save(*args, **kwargs)
 
        if not self.enrollment:
            owning_course = self.quiz.owning_course
            if owning_course:
                self.enrollment = Enrollment.objects.filter(
                    student=self.student,
                    course=owning_course
                ).first()
                if self.enrollment:
                    super().save(update_fields=['enrollment'])
 
        if self.enrollment and self.quiz.quiz_type == 'final':
            self.enrollment._sync_completion_status()


    def __str__(self):
        status = "Passed" if self.passed else "Failed"
        student_name = self.student.get_full_name() or self.student.email
        return f"{student_name} - {self.quiz.title} ({self.score or 'N/A'}% - {status})"


class StudentAnswer(models.Model):
    """
    Stores a student's chosen answer for a specific question within a quiz attempt.
    """
    attempt = models.ForeignKey(StudentQuizAttempt, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='student_answers')
    chosen_options = models.ManyToManyField(Option, related_name='chosen_by_students', blank=True)

    def __str__(self):
        # --- (!!!) UPDATED STRING (!!!) ---
        student_name = self.attempt.student.get_full_name() or self.attempt.student.email
        return f"{student_name}'s answer for {self.question.text[:30]}..."

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
        student_name = self.student.get_full_name() or self.student.email
        return f"Certificate for {student_name} - {self.course.title} (Issued: {self.issue_date})"
    
    def get_absolute_url(self):
        return reverse('view_certificate', kwargs={'certificate_id': self.certificate_id})

class Rating(models.Model):
    """
    Model to store course ratings and reviews.
    """
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='ratings')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='course_ratings')
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="A rating from 1 to 5 stars."
    )
    review = models.TextField(blank=True, null=True, help_text="Optional review text.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'course')
        ordering = ['-created_at']

    def __str__(self):
        user_name = self.user.get_full_name() or self.user.email
        return f'Rating for {self.course.title} by {user_name}'
    

class SupportTicket(models.Model):
    """
    Model to represent a support ticket submitted by a student.
    """
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('closed', 'Closed'),
    ]

    ticket_id = models.CharField(
        max_length=8, 
        unique=True, 
        verbose_name="Ticket ID", 
        help_text="A unique, automatically generated ticket identifier."
    )

    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='support_tickets')
    subject = models.CharField(max_length=200)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    resolution_note = models.TextField(verbose_name="Resolution Note", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.pk:
            self.ticket_id = self.generate_unique_ticket_id()
        
        super().save(*args, **kwargs)

    def generate_unique_ticket_id(self):
        """
        Generates a unique ticket ID in the format 'HL-XXXXX'.
        """
        prefix = 'HL-'
        length = 5
        chars = string.ascii_uppercase + string.digits
        while True:
            random_part = ''.join(random.choice(chars) for _ in range(length))
            new_ticket_id = f'{prefix}{random_part}'
            if not SupportTicket.objects.filter(ticket_id=new_ticket_id).exists():
                return new_ticket_id

    def __str__(self):
        return f"Ticket {self.ticket_id} - {self.subject} ({self.status})"
    
    class Meta:
        ordering = ['-created_at']


class CourseEvaluation(models.Model):
    enrollment = models.OneToOneField(Enrollment, on_delete=models.CASCADE, related_name='evaluation')
    
    # Ratings (1–5)
    career_relevance_rating = models.IntegerField(
        choices=[(i, i) for i in range(1, 6)], verbose_name="1. Relevance to Career Growth"
    )
    course_quality_rating = models.IntegerField(
        choices=[(i, i) for i in range(1, 6)], verbose_name="2. Course Content Quality"
    )
    instructor_effectiveness_rating = models.IntegerField(
        choices=[(i, i) for i in range(1, 6)], verbose_name="3. Instructor Effectiveness", null=True, blank=True
    )
    course_structure_rating = models.IntegerField(
        choices=[(i, i) for i in range(1, 6)], verbose_name="4. Course Structure & Organization", null=True, blank=True
    )
    
    actionable_feedback = models.TextField(
        verbose_name="5. How will you apply this learning to your job role?"
    )
    liked_most = models.TextField(verbose_name="6. What did you like most?", null=True, blank=True)
    improvement_suggestions = models.TextField(verbose_name="7. Suggestions for Improvement", null=True, blank=True)
    
    submitted_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Evaluation for {self.enrollment.course.title} by {self.enrollment.student.email}"


class CourseImportJob(models.Model):
    """
    Tracks the lifecycle of a single PDF-to-course import so the
    instructor gets real status/progress instead of an opaque
    synchronous request that can time out on large files.
    """
 
    STATUS_CHOICES = [
        ('queued', 'Queued'),
        ('extracting_text', 'Extracting Text'),
        ('extracting_images', 'Extracting Images'),
        ('generating_outline', 'Generating Course Outline'),
        ('generating_content', 'Generating Lesson Content'),
        ('generating_quiz', 'Generating Quiz Questions'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
 
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='course_import_jobs',
    )
    pdf_file = models.FileField(upload_to='course_imports/source_pdfs/')
    custom_title = models.CharField(max_length=200, blank=True, null=True)
    generate_quiz = models.BooleanField(default=True)
    requested_min_questions = models.PositiveIntegerField(default=20)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='queued')
    progress_percentage = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True, null=True)
 
    course = models.ForeignKey(
        'Course', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='import_job',
    )
 
    pages_processed = models.PositiveIntegerField(default=0)
    images_extracted = models.PositiveIntegerField(default=0)
    questions_generated = models.PositiveIntegerField(default=0)
 
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
 
    class Meta:
        ordering = ['-created_at']
 
    def __str__(self):
        return f"Import #{self.pk} ({self.status}) - {self.instructor.email}"
 
    def mark_failed(self, error: str):
        self.status = 'failed'
        self.error_message = error[:5000]
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'error_message', 'completed_at'])



class InstructorTraining(models.Model):
    """
    Tracks training assigned BY an admin/HR TO an instructor (not a student
    Enrollment — instructors are excluded from most Enrollment-related querysets
    by design, so this stays a separate, parallel model).
    """
    STATUS_CHOICES = [
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ]
 
    instructor = models.ForeignKey(
        'User', on_delete=models.CASCADE, related_name='assigned_trainings',
        limit_choices_to={'is_instructor': True}
    )
    course = models.ForeignKey(
        'Course', on_delete=models.SET_NULL, null=True, blank=True, related_name='instructor_trainings'
    )
    external_title = models.CharField(max_length=255, blank=True, null=True)
    external_url = models.URLField(blank=True, null=True)
 
    assigned_by = models.ForeignKey(
        'User', on_delete=models.SET_NULL, null=True, related_name='trainings_assigned_by_me'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='assigned')
    due_date = models.DateTimeField(null=True, blank=True)
    assigned_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    proof_file = models.FileField(upload_to='instructor_training_proofs/', blank=True, null=True)
    completion_note = models.TextField(blank=True, null=True)
 
    def clean(self):
        if not self.course and not (self.external_title and self.external_url):
            raise ValidationError(
                "Either an internal course, or both an external title and URL, must be provided."
            )
 
    def save(self, *args, **kwargs):
        self.full_clean()
        if self.status == 'completed' and not self.completed_at:
            self.completed_at = timezone.now()
        elif self.status != 'completed':
            self.completed_at = None
        super().save(*args, **kwargs)
 
    @property
    def training_title(self):
        return self.course.title if self.course else self.external_title
 
    def __str__(self):
        instructor_name = self.instructor.get_full_name() or self.instructor.email
        return f"{instructor_name} — {self.training_title} ({self.status})"
 
    class Meta:
        ordering = ['-assigned_at']


class ExternalTrainingResource(models.Model):
    PROVIDER_CHOICES = [
        ('ms_learn', 'Microsoft Learn'),
        ('cisco', 'Cisco'),
        ('sophos', 'Sophos'),
        ('linkedin_learning', 'LinkedIn Learning'),
        ('coursera', 'Coursera'),
        ('other', 'Other'),
    ]
    SOURCE_CHOICES = [
        ('synced', 'Auto-Synced'),      # currently only Microsoft Learn
        ('manual', 'Manually Curated'), # Cisco, Sophos, everything else today
    ]
 
    title = models.CharField(max_length=255)
    provider = models.CharField(max_length=30, choices=PROVIDER_CHOICES, default='ms_learn')
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default='manual')
    url = models.URLField()
    description = models.TextField(blank=True, null=True)
    tags = models.ManyToManyField('Tag', related_name='external_resources', blank=True)
 
    # --- Metadata only populated for synced (Microsoft Learn) content ---
    external_uid = models.CharField(
        max_length=255, blank=True, null=True,
        help_text="The provider's own content ID (e.g. MS Learn module UID). Used to dedupe on re-sync."
    )
    duration_minutes = models.PositiveIntegerField(blank=True, null=True)
    level = models.CharField(max_length=50, blank=True, null=True)   # beginner/intermediate/advanced
    product_area = models.CharField(max_length=255, blank=True, null=True)  # e.g. "Azure", "Microsoft 365"
    last_synced_at = models.DateTimeField(blank=True, null=True)
    added_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['provider', 'external_uid'],
                condition=models.Q(source='synced'),
                name='unique_synced_external_resource',
            )
        ]
 
    def __str__(self):
        return f"{self.title} ({self.get_provider_display()})"


class ExternalTrainingCompletion(models.Model):
    student = models.ForeignKey(
        'User', on_delete=models.CASCADE, related_name='external_training_completions',
        limit_choices_to={'is_student': True}
    )
    resource = models.ForeignKey(ExternalTrainingResource, on_delete=models.CASCADE, related_name='completions')
    completed_at = models.DateTimeField(auto_now_add=True)
    proof_file = models.FileField(upload_to='external_training_proofs/', blank=True, null=True)
    verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(
        'User', on_delete=models.SET_NULL, null=True, blank=True, related_name='external_completions_verified'
    )
 
    class Meta:
        unique_together = ('student', 'resource')
        ordering = ['-completed_at']
 
    def __str__(self):
        student_name = self.student.get_full_name() or self.student.email
        return f"{student_name} — {self.resource.title}"


class ReportLog(models.Model):
    REPORT_TYPE_CHOICES = [
        ('monthly_usage', 'Monthly Platform Usage Report'),
    ]
    report_type = models.CharField(max_length=30, choices=REPORT_TYPE_CHOICES)
    sent_at = models.DateTimeField(auto_now_add=True)
    recipient_emails = models.TextField(help_text="Comma-separated list of recipients.")
    period_start = models.DateField()
    period_end = models.DateField()
 
    def __str__(self):
        return f"{self.get_report_type_display()} ({self.period_start} to {self.period_end})"
 
    class Meta:
        ordering = ['-sent_at']
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
from django.utils.translation import gettext_lazy as _


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
        self.save()
    

class Course(models.Model):
    
    CATEGORY_CHOICES = [
        ('beginner', 'Beginner'),
        ('expert', 'Expert'),
        ('professional', 'Professional'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField()
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
    description = models.TextField(blank=True, null=True)
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
    )
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='contents')
    title = models.CharField(max_length=200)
    content_type = models.CharField(max_length=20, choices=CONTENT_TYPES)
    file = models.FileField(upload_to='lms_content/', blank=True, null=True, help_text="Upload video, PDF, or other files.")
    text_content = models.TextField(blank=True, null=True, help_text="For text-based content (e.g., notes).")
    video_url = models.URLField(max_length=500, blank=True, null=True, help_text="URL for external video (e.g., YouTube, Vimeo).")
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
    completed = models.BooleanField(default=False) # This will be managed by _sync_completion_status
    completed_at = models.DateTimeField(null=True, blank=True) # This will be managed by _sync_completion_status

    class Meta:
        unique_together = ('student', 'course')
        ordering = ['-enrolled_at']

    def __str__(self):
        student_name = self.student.get_full_name() or self.student.email
        return f"{student_name} enrolled in {self.course.title}"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    @property
    def progress_percentage(self):
        """Calculates the percentage of completed content (all non-quiz content) for this enrollment."""
        total_contents = Content.objects.filter(
            lesson__module__course=self.course
        ).count() 

        if total_contents == 0:
            return 0

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
            enrollment._sync_completion_status()


    def __str__(self):
        status = "Completed" if self.completed else "Incomplete"
        student_name = self.student.get_full_name() or self.student.email
        return f"{student_name} - {self.content.title} ({status})"


class Quiz(models.Model):
    """
    Represents a quiz, now linked directly to a Course.
    """
    course = models.OneToOneField(Course, on_delete=models.CASCADE, related_name='quiz', null=True, blank=True,
                                    help_text="The course this quiz is the main assessment for.")
    title = models.CharField(max_length=255)
    allow_multiple_correct = models.BooleanField(default=False)
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

        if not self.enrollment and self.quiz.course:
            self.enrollment = Enrollment.objects.filter(
                student=self.student,
                course=self.quiz.course
            ).first()
            if self.enrollment:
                super().save(update_fields=['enrollment']) 

        if self.enrollment:
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
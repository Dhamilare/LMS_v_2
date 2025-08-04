from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import *

# Inlines allow you to edit related objects on the same page as their parent.
class LessonInline(admin.TabularInline):
    """Inline to manage lessons directly from the Course admin page."""
    model = Lesson
    extra = 1
    fields = ('title', 'order', 'video_url', 'content', 'resource_file')
    prepopulated_fields = {'title': ('title',)}

class AssignmentInline(admin.TabularInline):
    """Inline to manage assignments directly from the Course admin page."""
    model = Assignment
    extra = 1
    fields = ('title', 'due_date', 'description')

class QuestionInline(admin.StackedInline):
    """Inline to manage questions directly from the Quiz admin page."""
    model = Question
    extra = 1

class ChoiceInline(admin.TabularInline):
    """Inline to manage choices directly from the Question admin page."""
    model = Choice
    extra = 4  # Provides 4 choices by default for each question
    fields = ('text', 'is_correct')


@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    """Custom admin for the User model to manage roles and user details."""
    list_display = ('username', 'email', 'role', 'is_staff', 'is_active', 'date_joined')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'role')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    ordering = ('-date_joined',)
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email', 'role')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    readonly_fields = ('date_joined', 'last_login')


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    """Admin for the Course model with inlines for lessons and assignments."""
    list_display = ('title', 'instructor', 'created_at')
    list_filter = ('instructor',)
    search_fields = ('title', 'description')
    inlines = [LessonInline, AssignmentInline]
    date_hierarchy = 'created_at'


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    """Admin for the Lesson model."""
    list_display = ('title', 'course', 'order')
    list_filter = ('course',)
    search_fields = ('title', 'content')
    list_editable = ('order',)
    raw_id_fields = ('course',)


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    """Admin for the Enrollment model."""
    list_display = ('student', 'course', 'enrollment_date', 'progress')
    list_filter = ('course', 'enrollment_date')
    search_fields = ('student__username', 'course__title')
    list_editable = ('progress',)
    raw_id_fields = ('student', 'course')


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    """Admin for the Assignment model."""
    list_display = ('title', 'course', 'due_date')
    list_filter = ('course', 'due_date')
    search_fields = ('title', 'description')
    date_hierarchy = 'due_date'


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    """Admin for the Submission model."""
    list_display = ('assignment', 'student', 'submission_date', 'grade', 'feedback')
    list_filter = ('assignment__course', 'student', 'grade')
    search_fields = ('assignment__title', 'student__username')
    list_editable = ('grade', 'feedback')
    readonly_fields = ('submission_date', 'file')


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    """Admin for the Certificate model."""
    list_display = ('student', 'course', 'issue_date')
    list_filter = ('course', 'issue_date')
    search_fields = ('student__username', 'course__title')
    raw_id_fields = ('student', 'course')


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Admin for the Notification model."""
    list_display = ('user', 'message', 'is_read', 'created_at')
    list_filter = ('is_read',)
    search_fields = ('user__username', 'message')
    date_hierarchy = 'created_at'
    list_editable = ('is_read',)


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    """Admin for the Quiz model with an inline for questions."""
    list_display = ('title', 'course', 'passing_score')
    list_filter = ('course',)
    search_fields = ('title',)
    inlines = [QuestionInline]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    """Admin for the Question model with an inline for choices."""
    list_display = ('text', 'quiz')
    list_filter = ('quiz',)
    inlines = [ChoiceInline]


@admin.register(QuizSubmission)
class QuizSubmissionAdmin(admin.ModelAdmin):
    """Admin for the QuizSubmission model."""
    list_display = ('quiz', 'student', 'score', 'submitted_at')
    list_filter = ('quiz', 'student')
    search_fields = ('quiz__title', 'student__username')
    readonly_fields = ('submitted_at',)
    raw_id_fields = ('quiz', 'student', 'choices')


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    """Admin for the Subscription model."""
    list_display = ('student', 'start_date', 'end_date', 'is_active', 'amount_paid')
    list_filter = ('is_active', 'start_date')
    search_fields = ('student__username',)


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    """Admin for the SupportTicket model."""
    list_display = ('subject', 'submitted_by', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('subject', 'submitted_by__username')
    date_hierarchy = 'created_at'
    list_editable = ('status',)


@admin.register(StudentProgress)
class StudentProgressAdmin(admin.ModelAdmin):
    """
    Customizes the admin for the StudentProgress model.
    """
    list_display = ('student', 'lesson', 'is_completed', 'completion_date')
    list_filter = ('lesson__course', 'is_completed')
    search_fields = ('student__username', 'lesson__title')
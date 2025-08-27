from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import *

# Custom User Admin
@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('is_instructor', 'is_student')}),
    )
    list_display = ('username', 'email', 'is_staff', 'is_instructor', 'is_student')
    list_filter = ('is_staff', 'is_instructor', 'is_student')

# Inline for Options within a Question
class OptionInline(admin.TabularInline):
    model = Option
    extra = 4  # Display 4 empty option forms
    min_num = 4 # Ensure at least 4 options are provided
    max_num = 4 # Ensure exactly 4 options are provided
    can_delete = False # Options are not typically deleted independently
    verbose_name_plural = "Options (Exactly 4, one must be correct)"

# Inline for Questions within a Quiz
class QuestionInline(admin.StackedInline):
    model = Question
    extra = 1 # Display 1 empty question form
    min_num = 1 # Ensure at least one question
    can_delete = True # Allow deleting questions
    verbose_name_plural = "Questions"

# Admin for Quiz model
@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ('title', 'course_link', 'pass_percentage', 'max_attempts', 'allow_multiple_correct', 'created_at')
    list_filter = ('course__title', 'pass_percentage', 'max_attempts', 'allow_multiple_correct')
    search_fields = ('title', 'description', 'course__title')
    inlines = [QuestionInline]


    def course_link(self, obj):
        if obj.course:
            return obj.course.title
        return "Not Assigned"
    course_link.short_description = "Assigned Course"

    fieldsets = (
        (None, {
            'fields': ('title', 'description', 'course', 'pass_percentage', 'max_attempts','allow_multiple_correct')
        }),
    )

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'quiz')
    inlines = [OptionInline]

# Admin for Course model
@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'instructor', 'price', 'is_published', 'created_at')
    list_filter = ('is_published', 'instructor')
    search_fields = ('title', 'category', 'description', 'instructor__username')
    prepopulated_fields = {'slug': ('title',)}

# Inline for Lessons within a Module
class LessonInline(admin.StackedInline):
    model = Lesson
    extra = 1
    show_change_link = True # Allows navigating to lesson details from module
    verbose_name_plural = "Lessons"

# Admin for Module model
@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'order')
    list_filter = ('course',)
    search_fields = ('title', 'description', 'course__title')
    inlines = [LessonInline]

# Inline for Content within a Lesson
class ContentInline(admin.StackedInline):
    model = Content
    extra = 1
    verbose_name_plural = "Contents"

# Admin for Lesson model
@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ('title', 'module', 'order')
    list_filter = ('module__course', 'module')
    search_fields = ('title', 'description', 'module__title', 'module__course__title')
    inlines = [ContentInline]

# Admin for Enrollment model
@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'enrolled_at', 'completed', 'completed_at')
    list_filter = ('completed', 'course', 'student')
    search_fields = ('student__username', 'course__title')
    raw_id_fields = ('student', 'course') # Use raw_id_fields for FKs to improve performance with many users/courses

# Admin for StudentContentProgress model
@admin.register(StudentContentProgress)
class StudentContentProgressAdmin(admin.ModelAdmin):
    list_display = ('student', 'content', 'completed', 'completed_at')
    list_filter = ('completed', 'content__lesson__module__course', 'student')
    search_fields = ('student__username', 'content__title')
    raw_id_fields = ('student', 'content')

# Admin for StudentQuizAttempt model
@admin.register(StudentQuizAttempt)
class StudentQuizAttemptAdmin(admin.ModelAdmin):
    list_display = ('student', 'quiz', 'score', 'passed', 'attempt_date', 'enrollment')
    list_filter = ('passed', 'quiz', 'student', 'quiz__course')
    search_fields = ('student__username', 'quiz__title', 'enrollment__course__title')
    raw_id_fields = ('student', 'quiz', 'enrollment')

# Admin for StudentAnswer model
@admin.register(StudentAnswer)
class StudentAnswerAdmin(admin.ModelAdmin):
    list_display = ('attempt', 'question', 'chosen_option')
    list_filter = ('attempt__quiz', 'question__quiz')
    search_fields = ('attempt__student__username', 'question__text', 'chosen_option__text')
    raw_id_fields = ('attempt', 'question', 'chosen_option')

# Admin for Certificate model
@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'issue_date', 'certificate_id')
    list_filter = ('course', 'student')
    search_fields = ('student__username', 'course__title', 'certificate_id')
    raw_id_fields = ('student', 'course')

@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ('course', 'user', 'rating', 'created_at')
    list_filter = ('rating', 'course', 'user')
    search_fields = ('course__title', 'user__username', 'review')
    raw_id_fields = ('course', 'user')


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'subject', 'student', 'status', 'resolution_note', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('subject', 'description', 'student__username', 'student__email')
    readonly_fields = ('student', 'created_at', 'updated_at')
    ordering = ('-created_at',)
    fieldsets = (
        (None, {
            'fields': ('subject', 'description', 'status', 'resolution_note'),
        }),
        ('Student Information', {
            'fields': ('student',),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )



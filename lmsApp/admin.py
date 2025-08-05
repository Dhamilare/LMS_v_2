from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import *

class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('is_instructor', 'is_student')}),
    )
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active', 'is_instructor', 'is_student')
    list_filter = ('is_staff', 'is_active', 'is_instructor', 'is_student')

admin.site.register(User, CustomUserAdmin)


# Inline for Modules within Course Admin
class ModuleInline(admin.TabularInline):
    model = Module
    extra = 1 # Number of empty forms to display
    show_change_link = True # Allow direct link to module edit page

# Inline for Lessons within Module Admin
class LessonInline(admin.TabularInline):
    model = Lesson
    extra = 1
    show_change_link = True

# Inline for Content within Lesson Admin
class ContentInline(admin.TabularInline):
    model = Content
    extra = 1
    show_change_link = True

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'instructor', 'price', 'is_published', 'created_at', 'updated_at', 'slug')
    list_filter = ('is_published', 'instructor')
    search_fields = ('title', 'description', 'instructor__username')
    prepopulated_fields = {'slug': ('title',)} # Auto-populate slug from title
    inlines = [ModuleInline]

@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'order')
    list_filter = ('course',)
    search_fields = ('title', 'description', 'course__title')
    inlines = [LessonInline]

@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ('title', 'module', 'order')
    list_filter = ('module__course', 'module')
    search_fields = ('title', 'description', 'module__title')
    inlines = [ContentInline]

@admin.register(Content)
class ContentAdmin(admin.ModelAdmin):
    list_display = ('title', 'lesson', 'content_type', 'order', 'created_at')
    list_filter = ('content_type', 'lesson__module__course', 'lesson__module', 'lesson')
    search_fields = ('title', 'text_content', 'video_url', 'lesson__title')

@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'enrolled_at', 'completed')
    list_filter = ('completed', 'course', 'student')
    search_fields = ('student__username', 'course__title')
    raw_id_fields = ('student', 'course') # Use raw_id_fields for FKs to improve performance with many users/courses

@admin.register(StudentContentProgress)
class StudentContentProgressAdmin(admin.ModelAdmin):
    list_display = ('student', 'content', 'completed', 'completed_at')
    list_filter = ('completed', 'content__lesson__module__course', 'student')
    search_fields = ('student__username', 'content__title')
    raw_id_fields = ('student', 'content')
    readonly_fields = ('completed_at',) # completed_at is set automatically by save method


class OptionInline(admin.TabularInline):
    model = Option
    extra = 0   # No extra blank forms
    min_num = 4 # Require exactly 4 options
    max_num = 4 # Allow exactly 4 options

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'quiz', 'order')
    list_filter = ('quiz',)
    search_fields = ('text', 'quiz__title')
    inlines = [OptionInline]
    raw_id_fields = ('quiz',) # Use raw_id_fields for FKs

class QuestionInline(admin.TabularInline):
    model = Question
    extra = 1
    show_change_link = True # Allow direct link to question edit page

@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ('title', 'lesson', 'duration_minutes', 'pass_percentage', 'created_at')
    list_filter = ('lesson__module__course', 'lesson')
    search_fields = ('title', 'description', 'lesson__title')
    inlines = [QuestionInline]
    raw_id_fields = ('lesson',) # Use raw_id_fields for OneToOneField

@admin.register(StudentQuizAttempt)
class StudentQuizAttemptAdmin(admin.ModelAdmin):
    list_display = ('student', 'quiz', 'score', 'passed', 'attempt_date')
    list_filter = ('passed', 'quiz', 'student')
    search_fields = ('student__username', 'quiz__title')
    raw_id_fields = ('student', 'quiz')

@admin.register(StudentAnswer)
class StudentAnswerAdmin(admin.ModelAdmin):
    list_display = ('attempt', 'question', 'chosen_option')
    list_filter = ('attempt__quiz', 'question__quiz')
    search_fields = ('attempt__student__username', 'question__text', 'chosen_option__text')
    raw_id_fields = ('attempt', 'question', 'chosen_option')

@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'issue_date', 'certificate_id', 'pdf_file')
    list_filter = ('issue_date', 'course', 'student')
    search_fields = ('student__username', 'course__title', 'certificate_id')
    readonly_fields = ('issue_date', 'certificate_id')
    raw_id_fields = ('student', 'course')
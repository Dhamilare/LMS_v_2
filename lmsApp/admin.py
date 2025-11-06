from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import *

# Custom User Admin
@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Personal info",
            {
                "fields": (
                    "first_name",
                    "last_name",
                )
            },
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        ("LMS Roles", {'fields': ('is_instructor', 'is_student')}), # Our custom fields
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    
    list_display = ('email', 'first_name', 'last_name', 'is_staff', 'is_instructor', 'is_student')
    list_filter = ('is_staff', 'is_instructor', 'is_student')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('email',)
    
    add_fieldsets = UserAdmin.add_fieldsets + (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'is_instructor', 'is_student'),
        }),
    )

class OptionInline(admin.TabularInline):
    model = Option
    extra = 4 
    min_num = 4
    max_num = 4
    can_delete = False
    verbose_name_plural = "Options (Exactly 4, one must be correct)"

class QuestionInline(admin.StackedInline):
    model = Question
    extra = 1
    min_num = 1
    can_delete = True
    verbose_name_plural = "Questions"


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
            'fields': ('title', 'description', 'course', 'pass_percentage', 'max_attempts','allow_multiple_correct', 'created_by')
        }),
    )
    
    readonly_fields = ('created_by',)

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'quiz')
    inlines = [OptionInline]

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'instructor', 'price', 'is_published', 'created_at')
    list_filter = ('is_published', 'instructor')
    search_fields = ('title', 'category', 'description', 'instructor__email', 'instructor__first_name', 'instructor__last_name')
    prepopulated_fields = {'slug': ('title',)}

class LessonInline(admin.StackedInline):
    model = Lesson
    extra = 1
    show_change_link = True
    verbose_name_plural = "Lessons"


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'order')
    list_filter = ('course',)
    search_fields = ('title', 'description', 'course__title')
    inlines = [LessonInline]


class ContentInline(admin.StackedInline):
    model = Content
    extra = 1
    verbose_name_plural = "Contents"


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ('title', 'module', 'order')
    list_filter = ('module__course', 'module')
    search_fields = ('title', 'description', 'module__title', 'module__course__title')
    inlines = [ContentInline]


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'enrolled_at', 'completed', 'completed_at')
    list_filter = ('completed', 'course', 'student')
    search_fields = ('student__email', 'student__first_name', 'student__last_name', 'course__title')
    raw_id_fields = ('student', 'course')


@admin.register(StudentContentProgress)
class StudentContentProgressAdmin(admin.ModelAdmin):
    list_display = ('student', 'content', 'completed', 'completed_at')
    list_filter = ('completed', 'content__lesson__module__course', 'student')
    search_fields = ('student__email', 'student__first_name', 'student__last_name', 'content__title')
    raw_id_fields = ('student', 'content')


@admin.register(StudentQuizAttempt)
class StudentQuizAttemptAdmin(admin.ModelAdmin):
    list_display = ('student', 'quiz', 'score', 'passed', 'attempt_date', 'enrollment')
    list_filter = ('passed', 'quiz', 'student', 'quiz__course')
    search_fields = ('student__email', 'student__first_name', 'student__last_name', 'quiz__title', 'enrollment__course__title')
    raw_id_fields = ('student', 'quiz', 'enrollment')

@admin.register(StudentAnswer)
class StudentAnswerAdmin(admin.ModelAdmin):
    list_display = ('attempt', 'question', 'display_chosen_options')
    list_filter = ('attempt__quiz', 'question__quiz')
    search_fields = ('attempt__student__email', 'attempt__student__first_name', 'attempt__student__last_name', 'question__text')
    raw_id_fields = ('attempt', 'question')

    def display_chosen_options(self, obj):
        return ", ".join([option.text for option in obj.chosen_options.all()])
    display_chosen_options.short_description = "Chosen Options"


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'issue_date', 'certificate_id')
    list_filter = ('course', 'student')
    search_fields = ('student__email', 'student__first_name', 'student__last_name', 'course__title', 'certificate_id')
    raw_id_fields = ('student', 'course')

@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ('course', 'user', 'rating', 'created_at')
    list_filter = ('rating', 'course', 'user')
    search_fields = ('course__title', 'user__email', 'user__first_name', 'user__last_name', 'review')
    raw_id_fields = ('course', 'user')


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'subject', 'student', 'status', 'resolution_note', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('subject', 'description', 'student__email', 'student__first_name', 'student__last_name')
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
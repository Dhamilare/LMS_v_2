from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib import messages
from .models import *
from django.db.models import Count
from django_ckeditor_5.widgets import CKEditor5Widget
from django import forms
from urllib.parse import urlencode
from django.shortcuts import redirect


# ==========================
# CKEditor5 Admin Integration
# ==========================
class CourseAdminForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = '__all__'
        widgets = {
            'description': CKEditor5Widget(config_name='default'),
        }

class ModuleAdminForm(forms.ModelForm):
    class Meta:
        model = Module
        fields = '__all__'
        widgets = {
            'description': CKEditor5Widget(config_name='default'),
        }

class LessonAdminForm(forms.ModelForm):
    class Meta:
        model = Lesson
        fields = '__all__'
        widgets = {
            'description': CKEditor5Widget(config_name='default'),
        }

class QuizAdminForm(forms.ModelForm):
    class Meta:
        model = Quiz
        fields = '__all__'
        widgets = {
            'description': CKEditor5Widget(config_name='default'),
        }



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
                    "department",
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
        ("LMS Roles", {'fields': ('is_instructor', 'is_student', 'is_hr')}), 
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    
    list_display = ('email', 'first_name', 'last_name', 'department', 'is_hr', 'is_staff', 'is_instructor', 'is_student')
    list_filter = ('is_staff', 'is_instructor', 'is_student', 'is_hr', 'department')
    search_fields = ('email', 'first_name', 'last_name', 'department')
    ordering = ('email',)
    
    add_fieldsets = UserAdmin.add_fieldsets + (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'department', 'is_instructor', 'is_student', 'is_hr'),
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
    form = QuizAdminForm
    list_display = ('title', 'quiz_type', 'target_link', 'pass_percentage', 'max_attempts', 'allow_multiple_correct', 'created_at')
    list_filter = ('quiz_type', 'course__title', 'pass_percentage', 'max_attempts', 'allow_multiple_correct')
    search_fields = ('title', 'description', 'course__title', 'module__title', 'module__course__title')
    inlines = [QuestionInline]

    raw_id_fields = ('course', 'module')

    def target_link(self, obj):
        """
        Shows what this quiz is attached to — a course (final assessment) or
        a module (knowledge check). Mirrors the old course_link() behavior for
        final quizzes, and extends it for module-level quizzes.
        """
        if obj.quiz_type == 'module_check' and obj.module:
            return f"{obj.module.course.title} → {obj.module.title} (module check)"
        if obj.course:
            return f"{obj.course.title} (final assessment)"
        return "Not Assigned"
    target_link.short_description = "Attached To"

    fieldsets = (
        (None, {
            'fields': ('title', 'description', 'quiz_type', 'course', 'module',
                       'pass_percentage', 'max_attempts', 'allow_multiple_correct', 'created_by'),
            'description': (
                "Set quiz_type to 'Final Course Assessment' and link a Course, OR "
                "'Module Knowledge Check' and link a Module — not both."
            ),
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
    form = CourseAdminForm
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
    form = ModuleAdminForm
    list_display = ('title', 'course', 'order', 'has_knowledge_check')
    list_filter = ('course',)
    search_fields = ('title', 'description', 'course__title')
    inlines = [LessonInline]

    def has_knowledge_check(self, obj):
        return hasattr(obj, 'quiz') and obj.quiz is not None
    has_knowledge_check.boolean = True
    has_knowledge_check.short_description = "Knowledge Check?"


class ContentInline(admin.StackedInline):
    model = Content
    extra = 1
    verbose_name_plural = "Contents"


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    form = LessonAdminForm
    list_display = ('title', 'module', 'order')
    list_filter = ('module__course', 'module')
    search_fields = ('title', 'description', 'module__title', 'module__course__title')
    inlines = [ContentInline]


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'enrolled_at', 'assignment_reason', 'completed', 'completed_at',
                     'reminder_7_sent', 'reminder_3_sent', 'followup_2mo_sent', 'followup_3mo_sent')
    list_filter = ('completed', 'assignment_reason', 'course', 'student')
    search_fields = ('student__email', 'student__first_name', 'student__last_name', 'course__title')
    raw_id_fields = ('student', 'course', 'assigned_by')


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


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "course_count")
    search_fields = ("name",)
    ordering = ("name",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(course_count=Count("courses"))

    def course_count(self, obj):
        return obj.course_count
    course_count.short_description = "Courses Using Tag"



@admin.register(CourseEvaluation)
class CourseEvaluationAdmin(admin.ModelAdmin):
    """
    Admin interface for reviewing mandatory course evaluations for appraisal.
    All fields are read-only to preserve the integrity of the student's submission.
    """
    
    # Columns shown in the main list view
    list_display = (
        'get_student_full_name',
        'get_course_title',
        'get_department',
        'career_relevance_rating',
        'course_quality_rating',
        'submitted_at',
    )
    
    # Filters available on the right sidebar
    list_filter = (
        'enrollment__course', 
        'enrollment__student__department',
        'submitted_at',
    )
    
    # Fields that can be searched
    search_fields = (
        'enrollment__student__first_name',
        'enrollment__student__last_name',
        'enrollment__student__email',
        'enrollment__course__title',
    )
    
    ordering = ('-submitted_at',)
    
    fieldsets = (
        (None, {
            'fields': ('enrollment', 'submitted_at')
        }),
        ('Ratings (1-5)', {
            'fields': ('career_relevance_rating', 'course_quality_rating', 'instructor_effectiveness_rating', 'course_structure_rating')
        }),
        ('Open Feedback (Qualitative)', {
            'fields': ('actionable_feedback', 'liked_most', 'improvement_suggestions')
        }),
    )
    
    # --- Custom Methods for List Display ---
    
    def get_student_full_name(self, obj):
        return obj.enrollment.student.get_full_name() or obj.enrollment.student.email
    get_student_full_name.short_description = 'Student'
    
    def get_course_title(self, obj):
        return obj.enrollment.course.title
    get_course_title.short_description = 'Course'

    def get_department(self, obj):
        return obj.enrollment.student.department or 'N/A'
    get_department.short_description = 'Department'

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser # Only superuser can delete evaluations

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]
    
    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        return False


# ===========================================================================
# Instructor-Led Training
# ===========================================================================
@admin.register(InstructorTraining)
class InstructorTrainingAdmin(admin.ModelAdmin):
    list_display = ('instructor', 'training_title', 'status', 'due_date', 'assigned_by', 'assigned_at', 'completed_at', 'has_proof')
    list_filter = ('status', 'assigned_at', 'due_date')
    search_fields = (
        'instructor__email', 'instructor__first_name', 'instructor__last_name',
        'course__title', 'external_title',
    )
    raw_id_fields = ('instructor', 'course', 'assigned_by')
    readonly_fields = ('assigned_at', 'completed_at')
    ordering = ('-assigned_at',)

    fieldsets = (
        (None, {
            'fields': ('instructor', 'assigned_by', 'status', 'due_date')
        }),
        ('Training Target (choose one)', {
            'fields': ('course', 'external_title', 'external_url'),
            'description': "Link an internal Course, OR fill in External Title + External URL — not both.",
        }),
        ('Completion', {
            'fields': ('proof_file', 'completion_note', 'completed_at'),
        }),
        ('Timestamps', {
            'fields': ('assigned_at',),
            'classes': ('collapse',),
        }),
    )

    def has_proof(self, obj):
        return bool(obj.proof_file)
    has_proof.boolean = True
    has_proof.short_description = "Proof Attached?"

    def save_model(self, request, obj, form, change):
        if not obj.pk and not obj.assigned_by:
            obj.assigned_by = request.user
        super().save_model(request, obj, form, change)


# ===========================================================================
# External Training Catalog
# ===========================================================================
@admin.register(ExternalTrainingResource)
class ExternalTrainingResourceAdmin(admin.ModelAdmin):
    list_display = ('title', 'provider', 'source', 'level', 'duration_minutes', 'is_active', 'last_synced_at', 'created_at')
    list_filter = ('provider', 'source', 'is_active')
    search_fields = ('title', 'description', 'external_uid', 'product_area')
    filter_horizontal = ('tags',)
    readonly_fields = ('last_synced_at', 'created_at')
    actions = ('curate_course_from_selected',)

    @admin.action(description="Curate an internal course from selected resource(s)")
    def curate_course_from_selected(self, request, queryset):
        resource_ids = list(queryset.values_list('id', flat=True))
        if not resource_ids:
            self.message_user(request, "Select at least one resource first.", level=messages.WARNING)
            return
        base_url = reverse('create_course_from_external_resources')
        query = urlencode({'resources': ','.join(str(i) for i in resource_ids)})
        return redirect(f"{base_url}?{query}")

    fieldsets = (
        (None, {
            'fields': ('title', 'provider', 'source', 'url', 'description', 'tags', 'is_active')
        }),
        ('Sync Metadata (Microsoft Learn only — leave blank for manual entries)', {
            'fields': ('external_uid', 'duration_minutes', 'level', 'product_area', 'last_synced_at'),
            'classes': ('collapse',),
        }),
        ('Ownership', {
            'fields': ('added_by', 'created_at'),
            'classes': ('collapse',),
        }),
    )

    def save_model(self, request, obj, form, change):
        if not obj.pk and not obj.added_by:
            obj.added_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(ExternalTrainingCompletion)
class ExternalTrainingCompletionAdmin(admin.ModelAdmin):
    list_display = ('student', 'resource', 'completed_at', 'verified', 'verified_by')
    list_filter = ('verified', 'resource__provider', 'completed_at')
    search_fields = (
        'student__email', 'student__first_name', 'student__last_name',
        'resource__title',
    )
    raw_id_fields = ('student', 'resource', 'verified_by')
    actions = ['verify_selected']

    @admin.action(description="Mark selected completions as verified")
    def verify_selected(self, request, queryset):
        updated = queryset.filter(verified=False).update(verified=True, verified_by=request.user)
        self.message_user(request, f"{updated} completion(s) marked as verified.", level=messages.SUCCESS)


# ===========================================================================
# Report Log 
# ===========================================================================
@admin.register(ReportLog)
class ReportLogAdmin(admin.ModelAdmin):
    list_display = ('report_type', 'period_start', 'period_end', 'sent_at')
    list_filter = ('report_type', 'sent_at')
    readonly_fields = ('report_type', 'sent_at', 'recipient_emails', 'period_start', 'period_end')
    ordering = ('-sent_at',)

    def has_add_permission(self, request):
        # Report logs are created only by the Celery task, never manually.
        return False

    def has_change_permission(self, request, obj=None):
        return False
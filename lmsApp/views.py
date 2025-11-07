from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string, get_template
from django.db.models import Q, Max, Count, Subquery, OuterRef, DecimalField
from django.db.models.functions import Coalesce
from django.urls import reverse
from .forms import *
from .models import *
from io import BytesIO
from xhtml2pdf import pisa
from django.conf import settings
import os
import traceback
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .utils import send_templated_email
from django.db.models import Prefetch
import csv
from django.db.models import Avg
from django.contrib.auth.models import Group
import random
from .utils import *
from django.contrib.sites.shortcuts import get_current_site 


def send_enrollment_email_to_instructor(request, enrollment):
    """
    Sends an email to the instructor of a course to notify them
    of a new student enrollment.
    """
    course = enrollment.course
    student = enrollment.student
    instructor = course.instructor

    # Only send email if an instructor is assigned to the course
    if instructor:
        # --- Get domain and protocol for email links ---
        current_site = get_current_site(request)
        protocol = 'https' if request.is_secure() else 'http'
        domain = current_site.domain
        current_year = timezone.now().year

        email_subject = f"New Enrollment for '{course.title}'"
        email_context = {
            'instructor_name': instructor.get_full_name() or instructor.email,
            'student_name': enrollment.student.get_full_name() or enrollment.student.email,
            'course_title': course.title,
            'enrollment_date': enrollment.enrolled_at.strftime('%Y-%m-%d'),
            'protocol': protocol,
            'domain': domain,
            'current_year': current_year,
            'dashboard_url': f"{protocol}://{domain}{reverse('dashboard')}",
        }
        
        send_templated_email(
            'emails/student_enrolled.html',
            email_subject,
            [instructor.email],
            email_context
        )


# --- Helper functions for role-based access control ---

def is_admin(user):
    return user.is_authenticated and user.is_staff

def is_instructor(user):
    return user.is_authenticated and user.is_instructor

def is_student(user):
    return user.is_authenticated and user.is_student

def is_ajax(request):
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'

# --- Authentication and Dashboard Views ---

# NEW: Simple view to render the login page
def login_view(request):
    """
    Renders the login page.
    Authentication is handled by social_django, this just shows the template.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'accounts/login.html')

# DELETED: student_register (Obsolete: Handled by Microsoft)
# DELETED: verify_email (Obsolete: Handled by Microsoft)
# DELETED: user_login (Obsolete: Handled by social_django)

@login_required
def user_logout(request):
    """
    Logs out the current user.
    """
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('login')


@login_required
def dashboard(request):
    """
    Displays the user's dashboard based on their role.
    Includes course search functionality and pagination for students.
    """
    user = request.user
    context = {
        'user': user,
        'is_admin': user.is_staff,
        'is_instructor': user.is_instructor,
        'is_student': user.is_student,
    }

    # --- ADMIN DASHBOARD LOGIC ---
    if user.is_staff:
        avg_score_subquery = Subquery(
            StudentQuizAttempt.objects.filter(
                quiz__course=OuterRef('pk')
            ).order_by()
            .values('quiz__course')
            .annotate(avg_score=Avg('score'))
            .values('avg_score'),
            output_field=models.DecimalField()
        )

        avg_rating_subquery = Subquery(
            Rating.objects.filter(
                course=OuterRef('pk')
            ).order_by()
            .values('course')
            .annotate(avg_rating=Avg('rating'))
            .values('avg_rating'),
            output_field=models.DecimalField()
        )

        total_certificates = Certificate.objects.count()
        total_students = User.objects.filter(is_student=True).count()
        total_platform_enrollments = Enrollment.objects.count()

        # Main annotated query to get course stats, ordered by popularity
        courses_queryset = Course.objects.annotate(
            total_enrollments=Count('enrollments', distinct=True),
            completed_enrollments=Count(
                'enrollments',
                filter=Q(enrollments__completed=True),
                distinct=True
            ),
            average_quiz_score=avg_score_subquery,
            average_rating=avg_rating_subquery
        ).order_by('-total_enrollments', 'title')

        # Pagination for the course list
        paginator = Paginator(courses_queryset, 4)
        page_number = request.GET.get('page')
        try:
            courses_page_obj = paginator.get_page(page_number)
        except (PageNotAnInteger, EmptyPage):
            courses_page_obj = paginator.page(1)

        # Build analytics per course for the paginated list
        courses_with_analytics = []

        for course in courses_page_obj:
            try:
                completion_rate = (
                    course.completed_enrollments / course.total_enrollments * 100
                    if course.total_enrollments > 0 else 0
                )

                courses_with_analytics.append({
                    'course': course,
                    'total_enrollments': course.total_enrollments,
                    'completion_rate': round(completion_rate, 2),
                    'average_quiz_score': (
                        round(course.average_quiz_score, 2)
                        if course.average_quiz_score is not None else 'N/A'
                    ),

                    'average_rating': (
                        round(course.average_rating, 2)
                        if course.average_rating is not None else 'N/A'
                    ),
                })
            except Exception as e:
                # Log the error and skip this course to prevent a page crash
                print(f"Error processing analytics for course ID {course.id}: {e}")
                courses_with_analytics.append({
                    'course': course,
                    'total_enrollments': 'N/A',
                    'completion_rate': 'N/A',
                    'average_quiz_score': 'N/A',
                    'average_rating': 'N/A',
                })

        # Global metric: Top 5 courses by average quiz score
        performance_insights = (
            StudentQuizAttempt.objects
            .values('quiz__course__title')
            .annotate(avg_score=Avg('score'))
            .order_by('-avg_score')[:5]
        )

        context.update({
            'total_platform_enrollments': total_platform_enrollments,
            'courses_with_analytics': courses_with_analytics,
            'courses_page_obj': courses_page_obj,
            'performance_insights': performance_insights,
            'total_students': total_students,
            'total_certificates': total_certificates
        })

    # --- INSTRUCTOR DASHBOARD LOGIC ---
    elif user.is_instructor:
        all_courses = Course.objects.filter(instructor=user).order_by('-created_at')
        context['courses'] = all_courses[:6]
        context['show_view_all_button'] = all_courses.count() > 6

    # --- STUDENT DASHBOARD LOGIC ---
    elif user.is_student:

        avg_rating_subquery = Subquery(
            Rating.objects.filter(
                course=OuterRef('course__pk')  # Links the subquery to the main queryset
            ).values('course').annotate(avg_rating=Avg('rating')).values('avg_rating'),
            output_field=DecimalField()
        )

        enrolled_courses_list = Enrollment.objects.filter(student=user).select_related('course').annotate(average_rating=avg_rating_subquery).order_by('-enrolled_at')

        # Apply pagination for enrolled courses
        enrolled_paginator = Paginator(enrolled_courses_list, 3) # 3 items per page
        enrolled_page_number = request.GET.get('enrolled_page') # Use 'enrolled_page' parameter for enrolled courses

        try:
            enrolled_page_obj = enrolled_paginator.get_page(enrolled_page_number)
        except Exception: # Catch PageNotAnInteger or EmptyPage
            enrolled_page_obj = enrolled_paginator.page(1)

        context['enrolled_courses'] = enrolled_page_obj # Pass the paginated object

        # --- Available Courses Search and Pagination Logic for students ---
        search_query = request.GET.get('q', '') # Get search query from 'q' parameter

        # Start with all published courses not yet enrolled by the student
        available_courses_queryset = Course.objects.filter(is_published=True).exclude(enrollments__student=user)

        if search_query:
            # Filter available courses by title or description if a search query exists
            available_courses_queryset = available_courses_queryset.filter(
                Q(title__icontains=search_query) | Q(description__icontains=search_query)
            ).distinct()
            context['search_query'] = search_query # Pass query back to template for input field

        # Apply pagination for available courses
        available_paginator = Paginator(available_courses_queryset, 6) # 6 items per page
        available_page_number = request.GET.get('available_page') # Use 'available_page' parameter for available courses

        try:
            available_page_obj = available_paginator.get_page(available_page_number)
        except Exception: # Catch PageNotAnInteger or EmptyPage
            available_page_obj = available_paginator.page(1)

        context['available_courses'] = available_page_obj # Pass the paginated object

    return render(request, 'dashboard.html', context)


# --- Admin Functionality ---

# DELETED: create_instructor (Obsolete: New workflow is Admin promote existing user)

@login_required
@user_passes_test(is_admin)
def instructor_list(request):
    """
    Admin view to list all instructors with added search and pagination.
    """
    query = request.GET.get('q', '')
    instructors_list = User.objects.filter(is_instructor=True)

    if query:
        # UPDATED: Search by email/name, not username
        instructors_list = instructors_list.filter(
            Q(email__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        )

    # UPDATED: Order by name
    instructors_list = instructors_list.order_by('first_name', 'last_name')

    paginator = Paginator(instructors_list, 10)  # Show 10 instructors per page
    page = request.GET.get('page')

    try:
        instructors = paginator.page(page)
    except PageNotAnInteger:
        instructors = paginator.page(1)
    except EmptyPage:
        instructors = paginator.page(paginator.num_pages)

    return render(request, 'admin/instructor_list.html', {
        'instructors': instructors,
        'query': query
    })

# DELETED: instructor_update (Obsolete: Handled by Django admin)

@login_required
@user_passes_test(is_admin)
def instructor_delete(request, pk):
    """
    Admin view to delete an instructor.
    NOTE: This deletes the User object. A softer approach might be to just
    set is_instructor=False. For now, we delete.
    """
    instructor = get_object_or_404(User, pk=pk, is_instructor=True)
    template_name = 'admin/_confirm_delete.html'

    if request.method == 'POST':
        if instructor == request.user: # Prevent admin from deleting themselves
            if is_ajax(request):
                return JsonResponse({'success': False, 'error': "You cannot delete your own account."})
            messages.error(request, "You cannot delete your own account.")
            return redirect('instructor_list')

        # UPDATED: Use full name in message
        instructor_name = instructor.get_full_name() or instructor.email
        instructor.delete()
        messages.success(request, f'Instructor "{instructor_name}" deleted successfully.')
        if is_ajax(request):
            return JsonResponse({'success': True, 'message': f'Instructor "{instructor_name}" deleted successfully!'})
        return redirect('instructor_list')

    context = {'object': instructor, 'type': 'instructor'}
    return render(request, template_name, context)

# --- Instructor Course Management ---

@login_required
@user_passes_test(is_instructor)
def course_list(request):
    """
    Lists courses managed by the logged-in instructor, with comprehensive search,
    category filtering, and pagination.
    """
    search_query = request.GET.get('q', '')
    selected_category = request.GET.get('category', '')
    courses = Course.objects.filter(instructor=request.user)

    if search_query:
        courses = courses.filter(
            Q(title__icontains=search_query) | Q(description__icontains=search_query)
        )

    if selected_category:
        courses = courses.filter(category=selected_category)

    courses = courses.annotate(
        total_enrollments=Count('enrollments')
    ).order_by('-created_at')

    paginator = Paginator(courses, 6)
    page_number = request.GET.get('page')

    try:
        page_obj = paginator.get_page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'selected_category': selected_category,
        'categories': Course.CATEGORY_CHOICES,
    }

    return render(request, 'instructor/course_list.html', context)


@login_required
def all_courses(request):
    """
    Displays a list of all published courses with comprehensive search and pagination,
    indicating the user's enrollment status for each course.
    """
    search_query = request.GET.get('q', '')
    courses_list = Course.objects.filter(is_published=True).annotate(average_rating=Avg('ratings__rating')).order_by('title')

    if search_query:
        courses_list = courses_list.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(instructor__first_name__icontains=search_query) |
            Q(instructor__last_name__icontains=search_query)
        ).distinct()

    enrolled_course_ids = set(Enrollment.objects.filter(student=request.user).values_list('course__id', flat=True))

    completed_course_slugs = set(Enrollment.objects.filter(
        student=request.user,
        completed=True
    ).values_list('course__slug', flat=True))

    courses_with_status = []
    for course in courses_list:
        courses_with_status.append({
            'course': course,
            'is_enrolled': course.id in enrolled_course_ids,
            'is_completed': course.slug in completed_course_slugs,
            'average_rating': course.average_rating
        })

    paginator = Paginator(courses_with_status, 6)
    page_number = request.GET.get('page')

    try:
        page_obj = paginator.get_page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    context = {
        'page_obj': page_obj,
        'search_query': search_query,
    }
    return render(request, 'student/courses.html', context)


@login_required
@user_passes_test(is_instructor)
def course_create(request):
    """
    Allows an instructor to create a new course.
    """
    template_name = 'instructor/course_form.html'

    if request.method == 'POST':
        form = CourseForm(request.POST, request.FILES)
        if form.is_valid():
            course = form.save(commit=False)
            course.instructor = request.user
            course.save()
            messages.success(request, f'Course "{course.title}" created successfully!')
            if is_ajax(request):
                return JsonResponse({'success': True, 'message': f'Course "{course.title}" created successfully!', 'redirect_url': str(course.get_absolute_url())})
            return redirect('course_detail', slug=course.slug)
        else:
            if is_ajax(request):
                form_html = render_to_string(template_name, {'form': form, 'page_title': 'Create New Course'}, request=request)
                return JsonResponse({'success': False, 'form_html': form_html, 'error': 'Validation failed.'})
            messages.error(request, 'Failed to create course. Please correct the errors.')
    else:
        form = CourseForm()
    return render(request, template_name, {'form': form, 'page_title': 'Create New Course'})


@login_required
@user_passes_test(is_instructor)
def course_update(request, slug):
    """
    Allows an instructor to update an existing course.
    """
    course = get_object_or_404(Course, slug=slug, instructor=request.user)
    template_name = 'instructor/_course_form.html' # Use partial for modals

    if request.method == 'POST':
        form = CourseForm(request.POST, request.FILES, instance=course)
        if form.is_valid():
            form.save()
            messages.success(request, f'Course "{course.title}" updated successfully!')
            if is_ajax(request):
                return JsonResponse({'success': True, 'message': f'Course "{course.title}" updated successfully!'})
            return redirect('course_detail', slug=course.slug)
        else:
            if is_ajax(request):
                form_html = render_to_string(template_name, {'form': form, 'page_title': f'Edit Course: {course.title}', 'course': course}, request=request)
                return JsonResponse({'success': False, 'form_html': form_html, 'error': 'Validation failed.'})
            messages.error(request, 'Failed to update course. Please correct the errors.')
    else:
        form = CourseForm(instance=course)
    return render(request, template_name, {'form': form, 'page_title': f'Edit Course: {course.title}', 'course': course})


@login_required
@user_passes_test(is_instructor)
def course_delete(request, slug):
    """
    Allows an instructor to delete a course.
    """
    course = get_object_or_404(Course, slug=slug, instructor=request.user)
    template_name = 'instructor/_confirm_delete.html'

    if request.method == 'POST':
        course.delete()
        messages.success(request, f'Course "{course.title}" deleted successfully.')
        if is_ajax(request):
            return JsonResponse({'success': True, 'message': f'Course "{course.title}" deleted successfully!', 'redirect_url': str(redirect('course_list').url)})
        return redirect('course_list')

    context = {'object': course, 'type': 'course', 'course_slug': course.slug}
    return render(request, template_name, context)


# --- Course Detail and Content Management Views ---
@login_required
def course_detail(request, slug):
    course = get_object_or_404(Course, slug=slug)
    is_enrolled = False
    enrollment = None

    if request.user.is_instructor and course.instructor != request.user:
        messages.error(request, "You do not have permission to view this course.")
        return redirect('dashboard')

    if request.user.is_student:
        enrollment = Enrollment.objects.filter(student=request.user, course=course).first()
        if enrollment:
            is_enrolled = True

        if not course.is_published and not is_enrolled:
            messages.error(request, "This course is not yet published or you are not enrolled.")
            return redirect('dashboard')

    modules_queryset = Module.objects.filter(course=course).order_by('order').prefetch_related(
        Prefetch('lessons', queryset=Lesson.objects.order_by('order').prefetch_related(
            Prefetch('contents', queryset=Content.objects.order_by('order')),
        ))
    )

    modules_data = []
    previous_module_completed = True

    for module in modules_queryset:
        module_accessible = False

        if request.user.is_instructor and course.instructor == request.user:
            module_accessible = True
        elif request.user.is_staff:
            module_accessible = True
        elif request.user.is_student and is_enrolled:
            if previous_module_completed:
                module_accessible = True

        current_module_is_completed = False
        if request.user.is_student and is_enrolled and module_accessible:
            current_module_is_completed = module.is_completed_by_student(request.user)

        lessons_data = []
        for lesson in module.lessons.all():
            contents_data = []
            for content_item in lesson.contents.all():
                content_is_completed = False
                if request.user.is_student and is_enrolled:
                    content_is_completed = content_item.is_completed_by_student(request.user)

                contents_data.append({
                    'id': content_item.id,
                    'title': content_item.title,
                    'content_type': content_item.content_type,
                    'is_completed': content_is_completed,
                    'get_content_type_display': content_item.get_content_type_display,
                })

            lesson_is_completed = False
            if request.user.is_student and is_enrolled:
                lesson_is_completed = lesson.is_completed_by_student(request.user)

            lessons_data.append({
                'id': lesson.id,
                'title': lesson.title,
                'description': lesson.description,
                'order': lesson.order,
                'contents': contents_data,
                'is_completed': lesson_is_completed,
            })

        modules_data.append({
            'id': module.id,
            'title': module.title,
            'description': module.description,
            'order': module.order,
            'lessons': lessons_data,
            'is_accessible': module_accessible,
            'is_completed': current_module_is_completed,
        })

        previous_module_completed = current_module_is_completed

    # Check for quiz status
    has_passed_final_quiz = False
    has_failed_course = False
    course_quiz = None
    if hasattr(course, 'quiz'):
        course_quiz = course.quiz
        if request.user.is_student and is_enrolled:
            has_passed_final_quiz = StudentQuizAttempt.objects.filter(
                student=request.user,
                quiz=course_quiz,
                passed=True
            ).exists()

            if course_quiz.max_attempts:
                total_attempts = StudentQuizAttempt.objects.filter(
                    student=request.user,
                    quiz=course_quiz
                ).count()

                if total_attempts >= course_quiz.max_attempts and not has_passed_final_quiz:
                    has_failed_course = True

    average_rating = Rating.objects.filter(course=course).aggregate(Avg('rating'))['rating__avg']
    total_ratings = Rating.objects.filter(course=course).count()
    user_rating = None
    if request.user.is_student and is_enrolled:
        user_rating = Rating.objects.filter(user=request.user, course=course).first()

    context = {
        'course': course,
        'modules': modules_data,
        'is_enrolled': is_enrolled,
        'enrollment': enrollment,
        'course_quiz': course_quiz,
        'has_passed_final_quiz': has_passed_final_quiz,
        'has_failed_course': has_failed_course,
        'average_rating': average_rating,
        'total_ratings': total_ratings,
        'user_rating': user_rating,
    }
    return render(request, 'course_detail.html', context)


@login_required
@require_POST
def rate_course(request, course_slug):
    course = get_object_or_404(Course, slug=course_slug)
    rating_value = request.POST.get('rating')
    review_text = request.POST.get('review')

    if not request.user.is_student:
        messages.error(request, "Only students can rate courses.")
        return redirect('course_detail', slug=course_slug)

    if not Enrollment.objects.filter(student=request.user, course=course).exists():
        messages.error(request, "You must be enrolled to rate this course.")
        return redirect('course_detail', slug=course_slug)

    if rating_value and review_text:
        rating, created = Rating.objects.update_or_create(
            user=request.user,
            course=course,
            defaults={'rating': rating_value, 'review': review_text}
        )
        messages.success(request, "Your rating has been submitted successfully!")
    else:
        messages.error(request, "Invalid rating or review.")

    return redirect('course_detail', slug=course_slug)


@login_required
@user_passes_test(is_instructor)
def module_create(request, course_slug):
    """
    Allows an instructor to add a new module to their course,
    automatically setting the order field.
    """
    course = get_object_or_404(Course, slug=course_slug, instructor=request.user)
    template_name = 'instructor/_module_form.html'

    if request.method == 'POST':
        form = ModuleForm(request.POST)
        if form.is_valid():
            module = form.save(commit=False)
            module.course = course
            max_order = Module.objects.filter(course=course).aggregate(Max('order'))['order__max']
            module.order = (max_order or 0) + 1
            
            module.save()
            messages.success(request, f'Module "{module.title}" added successfully to {course.title}.')
            if is_ajax(request):
                return JsonResponse({'success': True, 'message': f'Module "{module.title}" added successfully!'})
            return redirect('course_detail', slug=course.slug)
        else:
            if is_ajax(request):
                form_html = render_to_string(template_name, {'form': form, 'course': course, 'page_title': 'Add New Module'}, request=request)
                return JsonResponse({'success': False, 'form_html': form_html, 'error': 'Validation failed.'})
            messages.error(request, 'Failed to add module. Please correct the errors.')
    else:
        form = ModuleForm()
    return render(request, template_name, {'form': form, 'course': course, 'page_title': 'Add New Module'})


@login_required
@user_passes_test(is_instructor)
def module_update(request, course_slug, module_id):
    """
    Allows an instructor to update an existing module.
    """
    course = get_object_or_404(Course, slug=course_slug, instructor=request.user)
    module = get_object_or_404(Module, id=module_id, course=course)
    template_name = 'instructor/_module_form.html'

    if request.method == 'POST':
        form = ModuleForm(request.POST, instance=module)
        if form.is_valid():
            form.save()
            messages.success(request, f'Module "{module.title}" updated successfully.')
            if is_ajax(request):
                return JsonResponse({'success': True, 'message': f'Module "{module.title}" updated successfully!'})
            return redirect('course_detail', slug=course.slug)
        else:
            if is_ajax(request):
                form_html = render_to_string(template_name, {'form': form, 'course': course, 'page_title': f'Edit Module: {module.title}'}, request=request)
                return JsonResponse({'success': False, 'form_html': form_html, 'error': 'Validation failed.'})
            messages.error(request, 'Failed to update module. Please correct the errors.')
    else:
        form = ModuleForm(instance=module)
    return render(request, template_name, {'form': form, 'course': course, 'page_title': f'Edit Module: {module.title}'})


@login_required
@user_passes_test(is_instructor)
def module_delete(request, course_slug, module_id):
    course = get_object_or_404(Course, slug=course_slug, instructor=request.user)
    module = get_object_or_404(Module, id=module_id, course=course)
    template_name = 'instructor/_confirm_delete.html'

    if request.method == 'POST':
        module.delete()
        messages.success(request, f'Module "{module.title}" deleted successfully.')
        if is_ajax(request):
            return JsonResponse({'success': True, 'message': f'Module "{module.title}" deleted successfully!'})
        return redirect('course_detail', slug=course.slug)

    context = {'object': module, 'type': 'module', 'course_slug': course_slug}
    return render(request, template_name, context)


@login_required
@user_passes_test(is_instructor)
def lesson_create(request, course_slug, module_id):
    """
    Allows an instructor to add a new lesson to a module,
    automatically setting the order field.
    """
    course = get_object_or_404(Course, slug=course_slug, instructor=request.user)
    module = get_object_or_404(Module, id=module_id, course=course)
    template_name = 'instructor/_lesson_form.html'

    if request.method == 'POST':
        form = LessonForm(request.POST)
        if form.is_valid():
            lesson = form.save(commit=False)
            lesson.module = module
            max_order = Lesson.objects.filter(module=module).aggregate(Max('order'))['order__max']
            lesson.order = (max_order or 0) + 1
            
            lesson.save()
            messages.success(request, f'Lesson "{lesson.title}" added successfully to module "{module.title}".')
            if is_ajax(request):
                return JsonResponse({'success': True, 'message': f'Lesson "{lesson.title}" added successfully!'})
            return redirect('course_detail', slug=course.slug)
        else:
            if is_ajax(request):
                form_html = render_to_string(template_name, {'form': form, 'module': module, 'course': course, 'page_title': 'Add New Lesson'}, request=request)
                return JsonResponse({'success': False, 'form_html': form_html, 'error': 'Validation failed.'})
            messages.error(request, 'Failed to add lesson. Please correct the errors.')
    else:
        form = LessonForm()
    return render(request, template_name, {'form': form, 'module': module, 'course': course, 'page_title': 'Add New Lesson'})


@login_required
@user_passes_test(is_instructor)
def lesson_update(request, course_slug, module_id, lesson_id):
    """
    Allows an instructor to update an existing lesson.
    """
    course = get_object_or_404(Course, slug=course_slug, instructor=request.user)
    module = get_object_or_404(Module, id=module_id, course=course)
    lesson = get_object_or_404(Lesson, id=lesson_id, module=module)
    template_name = 'instructor/_lesson_form.html'

    if request.method == 'POST':
        form = LessonForm(request.POST, instance=lesson)
        if form.is_valid():
            form.save() 
            messages.success(request, f'Lesson "{lesson.title}" updated successfully.')
            if is_ajax(request):
                return JsonResponse({'success': True, 'message': f'Lesson "{lesson.title}" updated successfully!'})
            return redirect('course_detail', slug=course.slug)
        else:
            if is_ajax(request):
                form_html = render_to_string(template_name, {'form': form, 'module': module, 'course': course, 'page_title': f'Edit Lesson: {lesson.title}'}, request=request)
                return JsonResponse({'success': False, 'form_html': form_html, 'error': 'Validation failed.'})
            messages.error(request, 'Failed to update lesson. Please correct the errors.')
    else:
        form = LessonForm(instance=lesson)
    return render(request, template_name, {'form': form, 'module': module, 'course': course, 'page_title': f'Edit Lesson: {lesson.title}'})

@login_required
@user_passes_test(is_instructor)
def lesson_delete(request, course_slug, module_id, lesson_id):
    course = get_object_or_404(Course, slug=course_slug, instructor=request.user)
    module = get_object_or_404(Module, id=module_id, course=course)
    lesson = get_object_or_404(Lesson, id=lesson_id, module=module)
    template_name = 'instructor/_confirm_delete.html'

    if request.method == 'POST':
        lesson.delete()
        messages.success(request, f'Lesson "{lesson.title}" deleted successfully.')
        if is_ajax(request):
            return JsonResponse({'success': True, 'message': f'Lesson "{lesson.title}" deleted successfully!'})
        return redirect('course_detail', slug=course.slug)

    context = {'object': lesson, 'type': 'lesson', 'course_slug': course_slug, 'module_id': module_id}
    return render(request, template_name, context)


@login_required
@user_passes_test(is_instructor)
def content_create(request, course_slug, module_id, lesson_id):
    course = get_object_or_404(Course, slug=course_slug, instructor=request.user)
    module = get_object_or_404(Module, id=module_id, course=course)
    lesson = get_object_or_404(Lesson, id=lesson_id, module=module)
    template_name = 'instructor/_content_form.html'

    if request.method == 'POST':
        form = ContentForm(request.POST, request.FILES)
        if form.is_valid():
            content = form.save(commit=False)
            content.lesson = lesson

            max_order = Content.objects.filter(lesson=lesson).aggregate(Max('order'))['order__max']
            content.order = (max_order or 0) + 1

            content.save()
            messages.success(request, f'Content "{content.title}" added successfully to lesson "{lesson.title}".')
            if is_ajax(request):
                return JsonResponse({'success': True, 'message': f'Content "{content.title}" added successfully!'})
            return redirect('course_detail', slug=course.slug)
        else:
            if is_ajax(request):
                form_html = render_to_string(template_name, {'form': form, 'lesson': lesson, 'module': module, 'course': course, 'page_title': 'Add New Content'}, request=request)
                return JsonResponse({'success': False, 'form_html': form_html, 'error': 'Validation failed.'})
            messages.error(request, 'Failed to add content. Please correct the errors.')
    else:
        form = ContentForm()
    return render(request, template_name, {'form': form, 'lesson': lesson, 'module': module, 'course': course, 'page_title': 'Add New Content'})


@login_required
@user_passes_test(is_instructor)
def content_update(request, course_slug, module_id, lesson_id, content_id):
    course = get_object_or_404(Course, slug=course_slug, instructor=request.user)
    module = get_object_or_404(Module, id=module_id, course=course)
    lesson = get_object_or_404(Lesson, id=lesson_id, module=module)
    content = get_object_or_404(Content, id=content_id, lesson=lesson)
    template_name = 'instructor/_content_form.html'

    if request.method == 'POST':
        form = ContentForm(request.POST, request.FILES, instance=content)
        if form.is_valid():
            form.save()
            messages.success(request, f'Content "{content.title}" updated successfully.')
            if is_ajax(request):
                return JsonResponse({'success': True, 'message': f'Content "{content.title}" updated successfully!'})
            return redirect('course_detail', slug=course.slug)
        else:
            if is_ajax(request):
                form_html = render_to_string(template_name, {
                    'form': form, 'lesson': lesson, 'module': module, 'course': course, 'content': content,
                    'page_title': f'Edit Content: {content.title}'
                }, request=request)
                return JsonResponse({'success': False, 'form_html': form_html, 'error': 'Validation failed.'})
            messages.error(request, 'Failed to update content. Please correct the errors.')
    else:
        form = ContentForm(instance=content)

    return render(request, template_name, {
        'form': form, 'lesson': lesson, 'module': module, 'course': course, 'content': content,
        'page_title': f'Edit Content: {content.title}'
    })


@login_required
@user_passes_test(is_instructor)
def content_delete(request, course_slug, module_id, lesson_id, content_id):
    course = get_object_or_404(Course, slug=course_slug, instructor=request.user)
    module = get_object_or_404(Module, id=module_id, course=course)
    lesson = get_object_or_404(Lesson, id=lesson_id, module=module)
    content = get_object_or_404(Content, id=content_id, lesson=lesson)
    template_name = 'instructor/_confirm_delete.html'

    if request.method == 'POST':
        content.delete()
        messages.success(request, f'Content "{content.title}" deleted successfully.')
        if is_ajax(request):
            return JsonResponse({'success': True, 'message': f'Content "{content.title}" deleted successfully!'})
        return redirect('course_detail', slug=course.slug)

    context = {'object': content, 'type': 'content', 'course_slug': course_slug, 'module_id': module_id, 'lesson_id': lesson_id}
    return render(request, template_name, context)


@login_required
def content_detail(request, course_slug, module_id, lesson_id, content_id):
    course = get_object_or_404(Course, slug=course_slug)
    module = get_object_or_404(Module, id=module_id, course=course)
    lesson = get_object_or_404(Lesson, id=lesson_id, module=module)
    content = get_object_or_404(Content, id=content_id, lesson=lesson)
    student_progress = None

    if request.user.is_authenticated and request.user.is_student:
        student_progress, _ = StudentContentProgress.objects.get_or_create(
            student=request.user,
            content=content
        )

    can_view_content_page = False
    if request.user.is_authenticated:
        if request.user.is_instructor and course.instructor == request.user:
            can_view_content_page = True
        elif request.user.is_student and course.is_published and Enrollment.objects.filter(student=request.user, course=course).exists():
            can_view_content_page = True

    if not can_view_content_page:
        messages.error(request, "You do not have permission to view this content.")
        return redirect('dashboard')

    context = {
        'course': course,
        'module': module,
        'lesson': lesson,
        'content': content,
        'student_progress': student_progress,
    }
    return render(request, 'content_detail.html', context)


@login_required
@user_passes_test(is_student)
def enroll_course(request, slug):
    """
    Allows a student to enroll in a course.
    Handles:
    1. Student confirming an instructor-assigned course (via email link).
    2. Student self-enrolling from the application.
    """
    course = get_object_or_404(Course, slug=slug)
    student = request.user

    # Prevent enrollment in unpublished courses
    if not course.is_published:
        msg = 'Cannot enroll in an unpublished course.'
        if is_ajax(request):
            return JsonResponse({'success': False, 'error': msg}, status=400)
        messages.error(request, msg)
        return redirect('course_detail', slug=course.slug)

    try:
        with transaction.atomic():
            try:
                # Check if already enrolled
                enrollment = Enrollment.objects.get(student=student, course=course)
                action_message = 'You are already enrolled in this course.'
            except Enrollment.DoesNotExist:
                # New enrollment
                enrollment = Enrollment.objects.create(
                    student=student,
                    course=course
                )
                action_message = f'Successfully enrolled in "{course.title}"!'

            # --- Get domain and protocol for email links ---
            current_site = get_current_site(request)
            protocol = 'https' if request.is_secure() else 'http'
            domain = current_site.domain
            current_year = timezone.now().year

            # Always send instructor notification
            send_enrollment_email_to_instructor(request, enrollment) 

            # --- Send student confirmation email ---
            email_subject = f"Enrollment Confirmation: {course.title}"
            email_context = {
                'student_name': student.get_full_name() or student.email,
                'course_title': course.title,
                'instructor_name': course.instructor.get_full_name() or course.instructor.email,
                'enrollment_date': enrollment.enrolled_at.strftime('%B %d, %Y'),
                'course_url': request.build_absolute_uri(course.get_absolute_url()),
                'protocol': protocol,
                'domain': domain,
                'current_year': current_year,
            }
            send_templated_email(
                'emails/enrollment_confirmation.html',
                email_subject,
                [student.email],
                email_context
            )

            messages.success(request, action_message)

            if is_ajax(request):
                return JsonResponse({
                    'success': True,
                    'message': action_message,
                    'redirect_url': str(redirect('course_detail', slug=course.slug).url)
                })

            return redirect('course_detail', slug=course.slug)

    except Exception as e:
        messages.error(request, f'Failed to enroll in course: {e}')
        if is_ajax(request):
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
        return redirect('course_detail', slug=course.slug)


@login_required
@user_passes_test(is_student)
@require_POST
def mark_content_completed(request, course_slug, module_id, lesson_id, content_id):
    if not is_ajax(request):
        return JsonResponse({'success': False, 'error': 'Invalid request.'}, status=400)

    course = get_object_or_404(Course, slug=course_slug)
    content = get_object_or_404(Content, id=content_id, lesson__module__course=course)
    student = request.user

    if not Enrollment.objects.filter(student=student, course=course).exists():
        return JsonResponse({'success': False, 'error': 'You must be enrolled in this course to mark content.'}, status=403)

    try:
        progress, created = StudentContentProgress.objects.get_or_create(
            student=student,
            content=content,
            defaults={'completed': True, 'completed_at': timezone.now()}
        )
        if not created:
            progress.completed = not progress.completed
            progress.completed_at = timezone.now() if progress.completed else None
            progress.save()

        status_message = "marked as complete." if progress.completed else "marked as incomplete."
        messages.success(request, f'Content "{content.title}" {status_message}')
        return JsonResponse({'success': True, 'completed': progress.completed, 'message': f'Content {status_message}'})

    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Failed to update progress: {e}'}, status=500)


@login_required
@user_passes_test(is_student)
def quiz_take(request, course_slug):
    course = get_object_or_404(Course, slug=course_slug)
    quiz = get_object_or_404(Quiz, course=course)
    enrollment = get_object_or_404(Enrollment, student=request.user, course=course)

    if not course.is_published:
        messages.error(request, "This quiz is not currently available.")
        return redirect('course_detail', slug=course.slug)

    if not enrollment.is_content_completed:
        messages.error(request, "You must complete all course content before taking this assessment.")
        return redirect('course_detail', slug=course.slug)

    if not quiz.questions.exists():
        messages.info(request, "This quiz has no questions yet.")
        return redirect('course_detail', slug=course.slug)

    current_attempts_count = StudentQuizAttempt.objects.filter(student=request.user, quiz=quiz).count()

    if current_attempts_count >= quiz.max_attempts:
        has_passed_quiz = StudentQuizAttempt.objects.filter(
            student=request.user, quiz=quiz, passed=True
        ).exists()

        if has_passed_quiz:
            messages.success(request, f"You have already passed the quiz '{quiz.title}'.")
        else:
            messages.error(request, f"You have reached the maximum number of attempts ({quiz.max_attempts}) for this quiz and have not passed.")

        last_attempt = StudentQuizAttempt.objects.filter(student=request.user, quiz=quiz).order_by('-attempt_date').first()
        if last_attempt:
            return redirect('quiz_result', course_slug=course.slug, attempt_id=last_attempt.id)
        else:
            return redirect('course_detail', slug=course.slug)

    quiz_order_session_key = f'quiz_questions_order_{quiz.id}'
    quiz_answers_session_key = 'quiz_answers'

    if request.GET.get('new_attempt') or quiz_order_session_key not in request.session:
        random_question_ids = list(quiz.questions.values_list('id', flat=True).order_by('?'))
        request.session[quiz_order_session_key] = random_question_ids
        request.session[quiz_answers_session_key] = {}
        request.session.modified = True

    ordered_question_ids = request.session.get(quiz_order_session_key, [])
    quiz_answers = request.session.get(quiz_answers_session_key, {})

    questions = list(Question.objects.filter(id__in=ordered_question_ids))
    order_map = {id: i for i, id in enumerate(ordered_question_ids)}
    questions.sort(key=lambda q: order_map[q.id])

    page_number = request.GET.get('page', 1)
    try:
        page_number = int(page_number)
    except ValueError:
        page_number = 1

    paginator = Paginator(questions, 1)
    page_obj = paginator.get_page(page_number)
    current_question = page_obj.object_list[0]

    if request.method == 'POST':
        form = SingleQuestionForm(current_question, request.POST)

        if form.is_valid():
            field_name = f'question_{current_question.id}'
            chosen_answer = form.cleaned_data.get(field_name)

            request.session[quiz_answers_session_key][str(current_question.id)] = chosen_answer
            request.session.modified = True

            if page_obj.has_next():
                next_page_url = f'{reverse("quiz_take", args=[course.slug])}?page={page_obj.next_page_number()}'
                return redirect(next_page_url)
            else:
                return redirect('quiz_submit', course_slug=course.slug)
        else:
            messages.error(request, "Please correct the errors below.")

    else: # GET request
        initial_data = {}
        saved_answer = quiz_answers.get(str(current_question.id))
        if saved_answer:
            field_name = f'question_{current_question.id}'
            initial_data[field_name] = saved_answer

        form = SingleQuestionForm(current_question, initial=initial_data)

    context = {
        'course': course,
        'quiz': quiz,
        'form': form,
        'page_obj': page_obj,
        'current_attempts_count': current_attempts_count,
        'max_attempts': quiz.max_attempts,
        'attempts_remaining': quiz.max_attempts - current_attempts_count,
        'enrollment_id': enrollment.id,
    }
    return render(request, 'student/quiz_take.html', context)


@login_required
@user_passes_test(is_student)
def quiz_submit(request, course_slug):
    course = get_object_or_404(Course, slug=course_slug)
    quiz = get_object_or_404(Quiz, course=course)
    enrollment = get_object_or_404(Enrollment, student=request.user, course=course)

    if not course.is_published:
        messages.error(request, "You are not authorized to submit this quiz.")
        return redirect('course_detail', slug=course.slug)

    if not enrollment.is_content_completed:
        messages.error(request, "You must complete all course content before submitting this assessment.")
        return redirect('course_detail', slug=course.slug)

    current_attempts_count = StudentQuizAttempt.objects.filter(student=request.user, quiz=quiz).count()

    if current_attempts_count >= quiz.max_attempts:
        messages.error(request, f"You have already reached the maximum number of attempts ({quiz.max_attempts}) for this quiz.")
        last_attempt = StudentQuizAttempt.objects.filter(student=request.user, quiz=quiz).order_by('-attempt_date').first()
        if last_attempt:
            return redirect('quiz_result', course_slug=course.slug, attempt_id=last_attempt.id)
        else:
            return redirect('course_detail', slug=course.slug)

    quiz_answers = request.session.get('quiz_answers', {})
    if not quiz_answers:
        messages.error(request, "No answers found. Please try taking the quiz again.")
        return redirect('quiz_take', course_slug=course.slug)

    total_questions = quiz.questions.count()
    correct_answers_count = 0
    student_answers_to_create = []

    with transaction.atomic():
        attempt = StudentQuizAttempt.objects.create(
            student=request.user,
            quiz=quiz,
            enrollment=enrollment,
            score=0,
            passed=False
        )

        for question_key, chosen_option_ids in quiz_answers.items():
            question_id = int(question_key)
            question = get_object_or_404(Question, id=question_id, quiz=quiz)

            correct_options_ids_set = set(question.options.filter(is_correct=True).values_list('id', flat=True))

            if not isinstance(chosen_option_ids, list):
                chosen_option_ids = [chosen_option_ids]

            chosen_options_ids_set = set(int(id) for id in chosen_option_ids if id)

            if chosen_options_ids_set == correct_options_ids_set:
                correct_answers_count += 1

            student_answer = StudentAnswer(
                attempt=attempt,
                question=question
            )
            student_answers_to_create.append(student_answer)

        StudentAnswer.objects.bulk_create(student_answers_to_create)

        for question_key, chosen_option_ids in quiz_answers.items():
            if not isinstance(chosen_option_ids, list):
                chosen_option_ids = [chosen_option_ids]

            if chosen_option_ids:
                question_id = int(question_key)
                student_answer = get_object_or_404(StudentAnswer, attempt=attempt, question_id=question_id)
                chosen_options = Option.objects.filter(id__in=chosen_option_ids, question_id=question_id)
                student_answer.chosen_options.set(chosen_options)

        score_percentage = 0
        if total_questions > 0:
            score_percentage = (correct_answers_count / total_questions) * 100

        attempt.score = round(score_percentage, 2)
        attempt.passed = (score_percentage >= quiz.pass_percentage)
        attempt.save() # This will trigger the _sync_completion_status

    if 'quiz_answers' in request.session:
        del request.session['quiz_answers']

    messages.success(request, f'Quiz "{quiz.title}" submitted! Your score: {attempt.score:.2f}%')
    return redirect('quiz_result', course_slug=course.slug, attempt_id=attempt.id)


@login_required
@user_passes_test(is_student)
def quiz_result(request, course_slug, attempt_id):
    course = get_object_or_404(Course, slug=course_slug)
    quiz = get_object_or_404(Quiz, course=course)

    attempt = get_object_or_404(
        StudentQuizAttempt.objects.prefetch_related(
            Prefetch(
                'answers',
                queryset=StudentAnswer.objects.select_related('question').prefetch_related('chosen_options', 'question__options')
            )
        ),
        id=attempt_id,
        student=request.user,
        quiz=quiz
    )

    questions_with_answers = []
    student_answers_map = {sa.question_id: sa for sa in attempt.answers.all()}

    for question in quiz.questions.all().order_by('order'):
        student_answer = student_answers_map.get(question.id)
        correct_options_ids = set(question.options.filter(is_correct=True).values_list('id', flat=True))

        chosen_option_ids = set()
        if student_answer:
            chosen_option_ids = set(student_answer.chosen_options.values_list('id', flat=True))

        is_correct_question = (chosen_option_ids == correct_options_ids)

        options_data = []
        for option in question.options.all():
            options_data.append({
                'text': option.text,
                'id': option.id,
                'is_correct': option.is_correct,
                'is_chosen': option.id in chosen_option_ids,
            })

        question_data = {
            'question': question,
            'options': options_data,
            'is_correct': is_correct_question,
        }
        questions_with_answers.append(question_data)

    current_attempts_count = StudentQuizAttempt.objects.filter(
        student=request.user,
        quiz=quiz
    ).count()

    attempts_remaining = quiz.max_attempts - current_attempts_count
    can_retake = False
    if not attempt.passed and current_attempts_count < quiz.max_attempts:
        can_retake = True

    context = {
        'course': course,
        'quiz': quiz,
        'attempt': attempt,
        'questions_with_answers': questions_with_answers,
        'can_retake': can_retake,
        'current_attempts_count': current_attempts_count,
        'max_attempts': quiz.max_attempts,
        'attempts_remaining': attempts_remaining,
    }
    return render(request, 'student/quiz_result.html', context)


@login_required
@user_passes_test(is_student)
def issue_certificate(request, course_slug):
    """
    Allows a student to claim/issue a certificate for a completed course.
    Generates and saves the PDF, then sends a completion email with the PDF.
    """
    course = get_object_or_404(Course, slug=course_slug)
    student = request.user

    # Basic checks
    enrollment = get_object_or_404(Enrollment, student=student, course=course)

    if not enrollment.completed:
        messages.error(request, "You must complete the course to claim a certificate.")
        if is_ajax(request):
            return JsonResponse({'success': False, 'error': 'Course not completed.'}, status=400)
        return redirect('dashboard')

    if Certificate.objects.filter(student=student, course=course).exists():
        messages.info(request, "You have already claimed a certificate for this course.")
        certificate = Certificate.objects.get(student=student, course=course)
        
        if is_ajax(request):
            return JsonResponse({'success': True, 'message': 'Certificate already claimed.', 'redirect_url': str(redirect('view_certificate', certificate_id=certificate.certificate_id).url)})
        return redirect('view_certificate', certificate_id=certificate.certificate_id)

    try:
        with transaction.atomic():
            certificate = Certificate.objects.create(
                student=student,
                course=course,
            )
            
            # --- Get domain and protocol for email links ---
            current_site = get_current_site(request)
            protocol = 'https' if request.is_secure() else 'http'
            domain = current_site.domain
            current_year = timezone.now().year

            # --- PDF Generation Logic ---
            template_path = 'student/certificate_template.html'
            context = {
                'certificate': certificate,
                'student_name': student.get_full_name() or student.email, 
                'course_title': course.title,
                'instructor_name': course.instructor.get_full_name() or course.instructor.email, 
                'issue_date': certificate.issue_date,
                'certificate_id': certificate.certificate_id,
                'request': request, 
                'protocol': protocol, 
                'domain': domain, 
                'current_year': current_year, 
            }
            template = get_template(template_path)
            html = template.render(context)

            result_file = BytesIO()
            def link_callback(uri, rel):
                if uri.startswith(settings.MEDIA_URL):
                    path = os.path.join(settings.MEDIA_ROOT, uri.replace(settings.MEDIA_URL, ""))
                elif uri.startswith(settings.STATIC_URL):
                    path = os.path.join(settings.BASE_DIR, 'static', uri.replace(settings.STATIC_URL, ""))
                    if not os.path.exists(path): # Fallback for collected static files
                        path = os.path.join(settings.STATIC_ROOT, uri.replace(settings.STATIC_URL, ""))
                else:
                    path = uri # Assume it's a direct path or external URL
                return path

            pisa_status = pisa.CreatePDF(
                html,
                dest=result_file,
                link_callback=link_callback
            )

            if pisa_status.err:
                raise Exception(f"PDF generation error: {pisa_status.err}")

            # Save the PDF to the Certificate model's FileField
            file_name = f'certificate_{certificate.certificate_id}.pdf'
            certificate.pdf_file.save(file_name, result_file)
            certificate.save()
            # --- End PDF Generation Logic ---

            messages.success(request, f'Congratulations! Your certificate for "{course.title}" has been issued and sent to your email.')
            
            # --- Send Course Completion Email with PDF Attachment ---
            email_subject = f"Congratulations! You've Completed {course.title}!"
            email_context = {
                'student_name': student.get_full_name() or student.email,
                'course_title': course.title,
                'completion_date': certificate.issue_date,
                'certificate_url': f"{protocol}://{domain}{reverse('view_certificate', args=[certificate.certificate_id])}",
                'protocol': protocol,
                'domain': domain,
                'current_year': current_year,
            }
            
            # Prepare PDF attachment
            pdf_attachment = (
                f"{course.title}_Certificate_{certificate.certificate_id}.pdf",
                certificate.pdf_file.read(), # Read binary content of the saved PDF
                'application/pdf'
            )

            send_templated_email(
                'emails/course_completion.html',
                email_subject,
                [student.email],
                email_context,
                attachments=[pdf_attachment]
            )
            # --- End Email Send ---

            if is_ajax(request):
                return JsonResponse({'success': True, 'message': 'Certificate issued!', 'redirect_url': str(redirect('view_certificate', certificate_id=certificate.certificate_id).url)})
            return redirect('view_certificate', certificate_id=certificate.certificate_id)
    except Exception as e:
        messages.error(request, f'Failed to issue certificate: {e}')
        traceback.print_exc() # Print full traceback to console
        if is_ajax(request):
            return JsonResponse({'success': False, 'error': f'Failed to issue certificate: {e}'}, status=500)
        return redirect('dashboard')


@login_required
@user_passes_test(is_student)
def view_certificate(request, certificate_id):
    """
    Displays the certificate of completion (HTML) for a student.
    If ?download=true is in the URL, it serves the PDF file.
    """
    certificate = get_object_or_404(Certificate, certificate_id=certificate_id, student=request.user)
    
    # --- Check for download flag ---
    if request.GET.get('download') == 'true':
        if certificate.pdf_file and certificate.pdf_file.name:
            try:
                if certificate.pdf_file.storage.exists(certificate.pdf_file.name):
                    with certificate.pdf_file.open('rb') as pdf:
                        response = HttpResponse(pdf.read(), content_type='application/pdf')
                        response['Content-Disposition'] = f'attachment; filename="certificate_{certificate.certificate_id}.pdf"'
                        return response
                else:
                    messages.error(request, "PDF file not found. Please try generating it again.")
                    return redirect('course_detail', slug=certificate.course.slug)
            except Exception as e:
                messages.error(request, f"Error serving PDF: {e}.")
                return redirect('course_detail', slug=certificate.course.slug)
        else:
            messages.error(request, "No PDF file found for this certificate.")
            return redirect('course_detail', slug=certificate.course.slug)

    # --- Render HTML Page ---
    # Get domain and protocol for email links
    current_site = get_current_site(request)
    protocol = 'https' if request.is_secure() else 'http'
    domain = current_site.domain
    current_year = timezone.now().year

    context = {
        'certificate': certificate,
        'student_name': certificate.student.get_full_name() or certificate.student.email,
        'course_title': certificate.course.title,
        'instructor_name': certificate.course.instructor.get_full_name() or certificate.course.instructor.email,
        'issue_date': certificate.issue_date,
        'certificate_id': certificate.certificate_id,
        'protocol': protocol,
        'domain': domain, 
        'current_year': current_year,
    }
    return render(request, 'student/certificate_template.html', context)


@login_required
@user_passes_test(is_student)
def certificate_catalog(request):
    student_certificates = Certificate.objects.filter(student=request.user).order_by('-issue_date')
    context = {
        'student_certificates': student_certificates,
    }
    return render(request, 'student/certificate_catalog.html', context)


@login_required
@user_passes_test(is_admin)
def audit_logs(request):
    total_courses = Course.objects.count()
    total_enrollments = Enrollment.objects.count()
    total_students = User.objects.filter(is_student=True).count()
    total_completed_enrollments = Enrollment.objects.filter(completed=True).count()
    total_certificates_issued = Certificate.objects.count()

    enrollment_by_course_data = (
        Course.objects.annotate(
            enroll_count=Coalesce(Count('enrollments'), 0)
        )
        .order_by('-enroll_count')
    )
    course_labels = [course.title for course in enrollment_by_course_data]
    enrollment_counts = [course.enroll_count for course in enrollment_by_course_data]

    completion_status_counts = Enrollment.objects.aggregate(
        completed_count=Count('id', filter=Q(completed=True)),
        in_progress_count=Count('id', filter=Q(completed=False)),
    )
    completion_labels = ['Completed', 'In Progress']
    completion_data = [
        completion_status_counts.get('completed_count', 0) or 0,
        completion_status_counts.get('in_progress_count', 0) or 0,
    ]

    latest_attempts = StudentQuizAttempt.objects.filter(
        student_id=OuterRef('student_id'),
        quiz_id=OuterRef('quiz_id')
    ).order_by('-attempt_date').values('passed')[:1]

    students_with_attempts = StudentQuizAttempt.objects.annotate(
        latest_passed=Subquery(latest_attempts)
    ).values('student_id', 'latest_passed').distinct()

    passed_students = 0
    failed_students = 0
    attempted_students_set = set()

    for student_attempt in students_with_attempts:
        student_id = student_attempt['student_id']
        if student_id not in attempted_students_set:
            attempted_students_set.add(student_id)
            if student_attempt['latest_passed'] is True:
                passed_students += 1
            else:
                failed_students += 1

    courses_with_quizzes = Course.objects.filter(quiz__isnull=False)
    all_enrolled_students_count = Enrollment.objects.filter(
        course__in=courses_with_quizzes
    ).values('student_id').distinct().count()

    assessments_passed = passed_students
    assessments_failed = failed_students
    assessments_not_attempted = all_enrolled_students_count - (passed_students + failed_students)
    assessments_labels = ['Passed', 'Failed', 'Not Attempted']
    assessments_data = [assessments_passed, assessments_failed, assessments_not_attempted]

    all_enrollments = (
        Enrollment.objects.select_related('course', 'student', 'course__instructor')
        .order_by('-enrolled_at')
    )

    detailed_logs = []
    for enrollment in all_enrollments:
        certificate_status = "N/A"
        certificate_link = "#"
        if getattr(enrollment, "has_certificate", False):
            certificate_status = "Issued"
            if getattr(enrollment, "certificate_obj", None):
                certificate_link = enrollment.certificate_obj.get_absolute_url()
        elif getattr(enrollment, "can_claim_certificate", False):
            certificate_status = "Eligible (Claimable)"
        elif enrollment.completed:
            certificate_status = "Completed (No Certificate)"

        assessment_status = "No Quiz"
        if hasattr(enrollment.course, 'quiz'):
            has_attempts = StudentQuizAttempt.objects.filter(
                student=enrollment.student,
                quiz=enrollment.course.quiz
            ).exists()
            if has_attempts:
                assessment_status = "Passed" if enrollment.is_quiz_passed else "Failed"
            else:
                assessment_status = "Not Attempted"

        detailed_logs.append({
            'student_first_name': enrollment.student.first_name,
            'student_last_name': enrollment.student.last_name,
            # UPDATED: Use email as the key identifier, not username
            'student_email': enrollment.student.email,
            'course_title': enrollment.course.title,
            # UPDATED: Use email-safe name
            'instructor_name': enrollment.course.instructor.get_full_name() or enrollment.course.instructor.email,
            'enrolled_at': enrollment.enrolled_at.strftime("%b %d, %Y"),
            'completed_at': enrollment.completed_at.strftime("%b %d, %Y") if enrollment.completed_at else 'N/A',
            'is_completed': enrollment.completed,
            'progress_percentage': enrollment.progress_percentage,
            'certificate_status': certificate_status,
            'certificate_link': certificate_link,
            'assessment_status': assessment_status,
        })

    context = {
        'total_courses': total_courses,
        'total_students': total_students,
        'total_enrollments': total_enrollments,
        'total_completed_enrollments': total_completed_enrollments,
        'total_certificates_issued': total_certificates_issued,
        'course_labels_json': course_labels,
        'enrollment_counts_json': enrollment_counts,
        'completion_labels_json': completion_labels,
        'completion_data_json': completion_data,
        'assessments_labels_json': assessments_labels,
        'assessments_data_json': assessments_data,
        'detailed_logs_json': detailed_logs,
    }

    return render(request, 'admin/reporting.html', context)


@login_required
@user_passes_test(is_instructor)
def quiz_download_csv_template(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="quiz_questions_template.csv"'
    writer = csv.writer(response)
    writer.writerow([
        'question_text',
        'option1', 'is_correct1',
        'option2', 'is_correct2',
        'option3', 'is_correct3',
        'option4', 'is_correct4'
    ])
    return response


@login_required
@user_passes_test(is_instructor)
def quiz_list_instructor(request):
    quizzes = Quiz.objects.filter(created_by=request.user).order_by('-created_at')
    context = {'quizzes': quizzes}
    return render(request, 'instructor/quiz_list.html', context)


@login_required
@user_passes_test(is_instructor)
def quiz_edit(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id, created_by=request.user)

    if request.method == 'POST':
        form = QuizDetailsForm(request.POST, instance=quiz)
        if form.is_valid():
            form.save()
            return JsonResponse({
                'success': True,
                'message': f'Quiz "{quiz.title}" has been updated successfully!'
            })
        else:
            form_html = render_to_string(
                'instructor/partials/quiz_details_form.html',
                {'form': form, 'quiz': quiz},
                request=request
            )
            return JsonResponse({
                'success': False,
                'form_html': form_html
            }, status=400)
    else:
        form = QuizDetailsForm(instance=quiz)
        return render(request, 'instructor/partials/quiz_details_form.html', {'form': form, 'quiz': quiz})


@require_POST
@login_required
@user_passes_test(is_instructor)
def quiz_delete(request, quiz_id):
    try:
        quiz = get_object_or_404(Quiz, id=quiz_id, created_by=request.user)
        quiz_title = quiz.title
        quiz.delete()
        return JsonResponse({
            'success': True,
            'message': f'Quiz "{quiz_title}" and all its questions have been deleted successfully.'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'An error occurred while trying to delete the quiz: {str(e)}'
        }, status=400)


@login_required
@user_passes_test(is_instructor)
def quiz_create(request):
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'

    if request.method == 'POST':
        form = QuizDetailsForm(request.POST)
        if form.is_valid():
            quiz = form.save(commit=False)
            quiz.created_by = request.user
            quiz.save()
            return JsonResponse({
                'success': True,
                'message': f'Quiz "{quiz.title}" created successfully!',
                'quiz_id': quiz.id
            })
        else:
            if is_ajax:
                html_form = render_to_string('instructor/quiz_create.html', {'form': form}, request=request)
                return JsonResponse({'success': False, 'error': 'Validation failed.', 'form_html': html_form}, status=400)
    else:
        form = QuizDetailsForm()

    context = {'form': form}
    return render(request, 'instructor/quiz_create.html', context)


@login_required
@user_passes_test(is_instructor)
def quiz_detail_manage(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id, created_by=request.user)
    questions_list = quiz.questions.all().order_by('order')

    search_query = request.GET.get('q')
    if search_query:
        questions_list = questions_list.filter(
            Q(text__icontains=search_query) |
            Q(options__text__icontains=search_query)
        ).distinct()

    paginator = Paginator(questions_list, 10)
    page = request.GET.get('page')

    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    context = {
        'quiz': quiz,
        'page_obj': page_obj,
        'questions': page_obj.object_list,
        'search_query': search_query,
    }
    return render(request, 'instructor/quiz_detail_manage.html', context)


@login_required
@user_passes_test(is_instructor)
def question_create(request, quiz_id):
    # UPDATED: Simplified quiz lookup
    quiz = get_object_or_404(Quiz, id=quiz_id, created_by=request.user)

    if request.method == 'POST':
        form = QuestionForm(request.POST)
        option_formset = OptionFormSet(request.POST, prefix='options')

        if form.is_valid():
            question = form.save(commit=False)
            question.quiz = quiz
            option_formset.instance = question

            if option_formset.is_valid():
                with transaction.atomic():
                    question.save()
                    option_formset.save()
                return JsonResponse({'success': True, 'message': f'Question "{question.text[:30]}..." added successfully!'})
            else:
                form.option_formset = option_formset
                html_form = render_to_string('instructor/question_form.html', {'form': form, 'quiz': quiz}, request=request)
                return JsonResponse({'success': False, 'error': 'Please correct the errors in the options.', 'form_html': html_form}, status=400)
        else:
            html_form = render_to_string('instructor/question_form.html', {'form': form, 'quiz': quiz}, request=request)
            return JsonResponse({'success': False, 'error': 'Please correct the errors in the question.', 'form_html': html_form}, status=400)
    else:
        form = QuestionForm()
        form.option_formset = OptionFormSet(prefix='options')

    context = {'form': form, 'quiz': quiz}
    return render(request, 'instructor/question_form.html', context)


@login_required
@user_passes_test(is_instructor)
def question_update(request, quiz_id, question_id):
    # UPDATED: Simplified quiz lookup
    quiz = get_object_or_404(Quiz, id=quiz_id, created_by=request.user)
    question = get_object_or_404(Question, id=question_id, quiz=quiz)

    if request.method == 'POST':
        form = QuestionForm(request.POST, instance=question)
        option_formset = OptionFormSet(request.POST, instance=question, prefix='options')

        if form.is_valid():
            option_formset.instance = question

            if option_formset.is_valid():
                with transaction.atomic():
                    form.save()
                    option_formset.save()
                return JsonResponse({'success': True, 'message': f'Question "{question.text[:30]}..." updated successfully!'})
            else:
                form.option_formset = option_formset
                html_form = render_to_string('instructor/question_form.html', {'form': form, 'quiz': quiz, 'question': question}, request=request)
                return JsonResponse({'success': False, 'error': 'Please correct the errors in the options.', 'form_html': html_form}, status=400)
        else:
            html_form = render_to_string('instructor/question_form.html', {'form': form, 'quiz': quiz, 'question': question}, request=request)
            return JsonResponse({'success': False, 'error': 'Please correct the errors in the question.', 'form_html': html_form}, status=400)
    else:
        form = QuestionForm(instance=question)
        form.option_formset = OptionFormSet(instance=question, prefix='options')

    context = {'form': form, 'quiz': quiz, 'question': question}
    return render(request, 'instructor/question_form.html', context)


@login_required
@user_passes_test(is_instructor)
def question_delete(request, quiz_id, question_id):
    # UPDATED: Simplified quiz lookup
    quiz = get_object_or_404(Quiz, id=quiz_id, created_by=request.user)
    question = get_object_or_404(Question, id=question_id, quiz=quiz)

    if request.method == 'POST':
        try:
            with transaction.atomic():
                question.delete()
            return JsonResponse({'success': True, 'message': 'Question deleted successfully!'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Failed to delete question: {e}'}, status=400)
    return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=405)


@login_required
@user_passes_test(is_instructor)
def quiz_assign_to_course(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id, created_by=request.user) # Can only assign quizzes you created

    if request.method == 'POST':
        form = QuizAssignmentForm(request.POST, instructor_user=request.user)
        if form.is_valid():
            course = form.cleaned_data['course']

            if hasattr(course, 'quiz') and course.quiz:
                return JsonResponse({'success': False, 'error': f'Course "{course.title}" already has a quiz assigned.'}, status=400)

            quiz.course = course
            quiz.save()
            return JsonResponse({'success': True, 'message': f'Quiz "{quiz.title}" assigned to course "{course.title}" successfully!'})
        else:
            html_form = render_to_string('instructor/quiz_assign_form.html', {'form': form, 'quiz': quiz}, request=request)
            return JsonResponse({'success': False, 'error': 'Validation failed.', 'form_html': html_form}, status=400)
    else:
        initial_data = {}
        if quiz.course:
            initial_data['course'] = quiz.course.id
        form = QuizAssignmentForm(initial=initial_data, instructor_user=request.user)

    context = {'form': form, 'quiz': quiz}
    return render(request, 'instructor/quiz_assign_form.html', context)


@login_required
@user_passes_test(is_instructor)
def quiz_upload_csv(request, quiz_id):
    # UPDATED: Simplified quiz lookup
    quiz = get_object_or_404(Quiz, id=quiz_id, created_by=request.user)

    if request.method == 'POST':
        form = CSVUploadForm(request.POST, request.FILES)
        if not form.is_valid():
            html_form = render_to_string('instructor/quiz_upload_csv.html', {'form': form, 'quiz': quiz}, request=request)
            return JsonResponse({
                'success': False, 'error': 'Validation failed.',
                'form_errors': form.errors.as_json(), 'form_html': html_form
            }, status=400)

        csv_file = request.FILES.get('csv_file')
        if not csv_file:
            return JsonResponse({'success': False, 'error': 'No file was uploaded.'}, status=400)
        if not csv_file.name.lower().endswith('.csv'):
            return JsonResponse({'success': False, 'error': 'File is not a CSV.'}, status=400)

        questions_buffer = []
        options_buffer = []

        try:
            with transaction.atomic():
                max_order = quiz.questions.aggregate(models.Max('order'))['order__max'] or 0
                try:
                    file_data = csv_file.read().decode('utf-8').splitlines()
                except UnicodeDecodeError:
                    return JsonResponse({'success': False, 'error': 'Unable to decode the CSV file. Ensure it is UTF-8 encoded.'}, status=400)

                reader = csv.reader(file_data)
                header = next(reader, None)
                if header is None:
                    raise ValueError('The CSV file is empty.')

                for i, row in enumerate(reader):
                    row_number = i + 2
                    if len(row) != 9:
                        raise ValueError(f'Row {row_number}: Expected 9 columns, got {len(row)}.')

                    question_text = row[0].strip()
                    if not question_text:
                        raise ValueError(f'Row {row_number}: Question text cannot be empty.')

                    new_question = Question(quiz=quiz, text=question_text, order=max_order + i + 1)
                    questions_buffer.append(new_question)
                    correct_options_count = 0

                    for j in range(1, 9, 2):
                        option_text = row[j].strip()
                        is_correct_str = row[j + 1].strip().lower()
                        is_correct = is_correct_str in ['true', '1', 'yes']

                        if not option_text:
                            raise ValueError(f'Row {row_number}, Option {(j // 2) + 1}: Option text cannot be empty.')
                        if is_correct:
                            correct_options_count += 1

                        options_buffer.append({
                            'question_index': i,
                            'text': option_text,
                            'is_correct': is_correct
                        })

                    if correct_options_count == 0:
                        raise ValueError(f'Row {row_number}: Each question must have at least one correct option.')
                    if not quiz.allow_multiple_correct and correct_options_count > 1:
                        raise ValueError(f'Row {row_number}: This quiz allows only one correct option, but {correct_options_count} were found.')

                questions_buffer = Question.objects.bulk_create(questions_buffer)

                final_options = [
                    Option(
                        question=questions_buffer[opt['question_index']],
                        text=opt['text'],
                        is_correct=opt['is_correct']
                    ) for opt in options_buffer
                ]
                Option.objects.bulk_create(final_options)

        except ValueError as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'An unexpected error occurred: {str(e)}'}, status=500)

        return JsonResponse({'success': True, 'message': f'{len(questions_buffer)} questions uploaded successfully!'})

    form = CSVUploadForm()
    context = {'form': form, 'quiz': quiz}
    return render(request, 'instructor/quiz_upload_csv.html', context)


@login_required
@user_passes_test(is_instructor)
def quiz_download_csv_template_view(request, quiz_id): # Renamed view
    quiz = get_object_or_404(Quiz, id=quiz_id, created_by=request.user)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="quiz_{quiz_id}_questions_template.csv"'
    response.write('\ufeff'.encode('utf-8')) # BOM for Excel

    writer = csv.writer(response)
    writer.writerow([
        'question_text',
        'option1', 'is_correct1',
        'option2', 'is_correct2',
        'option3', 'is_correct3',
        'option4', 'is_correct4'
    ])

    if quiz.allow_multiple_correct:
        note = "Example: Multiple correct answers allowed (use True/False, case-insensitive)"
        sample_question = [
            'Which of the following are programming languages?',
            'Python', 'True', 'HTML', 'False', 'Java', 'True', 'CSS', 'False'
        ]
    else:
        note = "Example: Only one correct answer allowed (use True for correct, False for others)"
        sample_question = [
            'What is the capital of France?',
            'Paris', 'True', 'London', 'False', 'Berlin', 'False', 'Rome', 'False'
        ]

    writer.writerow([note] + [''] * 7)
    writer.writerow(sample_question)
    return response


@login_required
@user_passes_test(is_student)
def course_transcript(request, course_slug):
    course = get_object_or_404(Course, slug=course_slug)
    enrollment = get_object_or_404(Enrollment, student=request.user, course=course)

    final_quiz = None
    has_passed_final_quiz = False
    if hasattr(course, 'quiz'):
        final_quiz = course.quiz
        has_passed_final_quiz = StudentQuizAttempt.objects.filter(
            student=request.user,
            quiz=final_quiz,
            passed=True
        ).exists()

    course_quizzes = Quiz.objects.filter(course=course)
    attempts = StudentQuizAttempt.objects.filter(
        student=request.user,
        quiz__in=course_quizzes
    ).order_by('attempt_date')

    average_score = attempts.aggregate(Avg('score'))['score__avg']

    context = {
        'course': course,
        'enrollment': enrollment,
        'attempts': attempts,
        'average_score': average_score,
        'has_passed_final_quiz': has_passed_final_quiz,
    }
    return render(request, 'student/course_transcript.html', context)


@user_passes_test(is_instructor)
def assign_course_to_student_view(request):
    """
    Handles assigning a course to a student via AJAX form.

    Sends:
    - Email to the student (they’ve been assigned a course)
    - Email to the instructor who assigned it (confirmation)
    """
    if request.method == 'POST':
        form = AssignCourseForm(request.POST)
        if form.is_valid():
            
            try:
                with transaction.atomic():
                    enrollment, created = Enrollment.objects.get_or_create(
                        student=form.cleaned_data['student'],
                        course=form.cleaned_data['course'],
                        defaults={'completed': False}
                    )

                    # Check if student is already enrolled
                    if not created:
                        if enrollment.completed:
                            return JsonResponse({'success': False, 'message': 'Student is already enrolled in and has completed this course.'}, status=400)
                        else:
                            return JsonResponse({'success': False, 'message': 'Student is already enrolled in this course.'}, status=400)

                    # --- If we are here, the enrollment was just created ---
                    student = enrollment.student
                    course = enrollment.course
                    assigner = request.user
                    
                    # --- Get domain and protocol for email links ---
                    current_site = get_current_site(request)
                    protocol = 'https' if request.is_secure() else 'http'
                    domain = current_site.domain
                    current_year = timezone.now().year

                    # --- Email to student ---
                    student_context = {
                        'student_name': student.get_full_name() or student.email,
                        'course_title': course.title,
                        'course_url': request.build_absolute_uri(course.get_absolute_url()),
                        'assigned_by': assigner.get_full_name() or assigner.email,
                        'protocol': protocol,
                        'domain': domain,
                        'current_year': current_year,
                    }
                    send_templated_email(
                        'emails/course_assigned.html',
                        'You have been assigned a new course!',
                        [student.email],
                        student_context
                    )

                    # --- Email to instructor (assigner) ---
                    instructor_context = {
                        'instructor_name': assigner.get_full_name() or assigner.email,
                        'student_name': student.get_full_name() or student.email,
                        'course_title': course.title,
                        'assignment_date': timezone.now().strftime('%B %d, %Y'),
                        'course_url': request.build_absolute_uri(course.get_absolute_url()),
                        'protocol': protocol,
                        'domain': domain,
                        'current_year': current_year,
                    }
                    send_templated_email(
                        'emails/course_assigned_confirmation.html',
                        f"Course '{course.title}' successfully assigned!",
                        [assigner.email],
                        instructor_context
                    )

                    return JsonResponse({'success': True, 'message': f"Course '{course.title}' assigned to {student.get_full_name()} and confirmation sent to you."})

            except Exception as e:
                print(f"Error in assign_course_to_student_view: {e}")
                return JsonResponse({'success': False, 'message': f'An unexpected error occurred: {str(e)}'}, status=500)

        else:
            errors_json = form.errors.as_json()
     
            return JsonResponse({'success': False, 'message': 'Validation failed. Please check the form.', 'errors': errors_json}, status=400)
    form = AssignCourseForm()
    return render(request, 'instructor/student_assign_form.html', {'form': form})


@user_passes_test(is_instructor)
def assign_course_page_view(request):
    all_enrollments = Enrollment.objects.filter(
        course__instructor=request.user
    ).select_related('student', 'course').order_by('-enrolled_at')

    search_query = request.GET.get('q', '')
    if search_query:
        all_enrollments = all_enrollments.filter(
            # UPDATED: Search by email/name
            Q(student__first_name__icontains=search_query) |
            Q(student__last_name__icontains=search_query) |
            Q(student__email__icontains=search_query) |
            Q(course__title__icontains=search_query)
        )

    chart_labels = []
    chart_datasets = []

    def get_random_color():
        r = random.randint(0, 255)
        g = random.randint(0, 255)
        b = random.randint(0, 255)
        return f'rgba({r}, {g}, {b}, 0.8)'

    enrolled_courses = {enrollment.course for enrollment in all_enrollments}
    all_modules = Module.objects.filter(course__in=enrolled_courses).order_by('title').distinct()
    module_content_counts = {
        module.id: Content.objects.filter(lesson__module=module).count()
        for module in all_modules
    }

    enrollment_list = list(all_enrollments)
    for enrollment in enrollment_list:
        # UPDATED: Use email-safe name
        student_name = enrollment.student.get_full_name() or enrollment.student.email
        chart_labels.append(student_name)

    for module in all_modules:
        module_progress_data = []
        total_content_in_module = module_content_counts.get(module.id, 0)

        for enrollment in enrollment_list:
            student_progress_count = None
            if module.course == enrollment.course:
                if total_content_in_module > 0:
                    completed_content_count = StudentContentProgress.objects.filter(
                        student=enrollment.student,
                        content__lesson__module=module
                    ).count()
                    student_progress_count = (completed_content_count / total_content_in_module) * 100
                else:
                    student_progress_count = 0
            module_progress_data.append(round(student_progress_count, 2) if student_progress_count is not None else None)

        chart_datasets.append({
            'label': module.title,
            'data': module_progress_data,
            'backgroundColor': get_random_color(),
        })

    if not chart_labels:
        chart_data = {'labels': ['No Students'], 'datasets': [{'label': 'Progress', 'data': [0], 'backgroundColor': ['#9CA3AF']}]}
    else:
        chart_data = {'labels': chart_labels, 'datasets': chart_datasets}

    paginator = Paginator(all_enrollments, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'chart_data': chart_data,
        'form': AssignCourseForm(),
    }
    return render(request, 'instructor/course_assign.html', context)


@login_required
@user_passes_test(is_admin)
def student_list_view(request):
    # UPDATED: Order by name
    all_students = User.objects.filter(is_student=True).order_by('first_name', 'last_name')

    query = request.GET.get('q')
    if query:
        all_students = all_students.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query)
        ).distinct()

    paginator = Paginator(all_students, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'total_students': all_students.count(),
        'query': query,
    }
    return render(request, 'admin/student_list.html', context)


@login_required
def submit_ticket(request):
    if request.method == 'POST':
        form = SupportTicketForm(request.POST)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.student = request.user
            ticket.save()

            student_context = {
                'ticket': ticket,
                'username': request.user.get_full_name() or request.user.email,
                'current_year': timezone.now().year,
                'request': request,
            }
            send_templated_email(
                'emails/ticket_confirmation.html',
                f'Confirmation: Support Request #{ticket.ticket_id}',
                [request.user.email],
                student_context
            )

            admin_users = User.objects.filter(is_staff=True, is_active=True).values_list('email', flat=True)
            admin_emails = [email for email in admin_users if email]

            if admin_emails:
                current_site = get_current_site(request)
                admin_context = {
                    'ticket': ticket,
                    'current_year': timezone.now().year,
                    'domain': current_site.domain,
                    'protocol': 'https' if request.is_secure() else 'http',
                }
                send_templated_email(
                    'emails/admin_ticket_notification.html',
                    f'NEW Support Request:#{ticket.ticket_id}',
                    admin_emails,
                    admin_context
                )
            return redirect('ticket_detail', ticket_id=ticket.ticket_id)
    else:
        form = SupportTicketForm()
    return render(request, 'student/submit_ticket.html', {'form': form})


@login_required
def ticket_list(request):
    if not is_student(request.user):
        return redirect('dashboard')

    query = request.GET.get('q', '')
    status_filter = request.GET.get('status')
    tickets = SupportTicket.objects.filter(student=request.user).order_by('-created_at')

    if query:
        tickets = tickets.filter(
            Q(subject__icontains=query) |
            Q(description__icontains=query)
        ).distinct()
    if status_filter:
        tickets = tickets.filter(status=status_filter)

    paginator = Paginator(tickets, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {'page_obj': page_obj, 'query': query}
    return render(request, 'student/ticket_list.html', context)


@login_required
def ticket_detail(request, ticket_id):
    if not is_student(request.user):
        return redirect('dashboard')
    ticket = get_object_or_404(SupportTicket, ticket_id=ticket_id, student=request.user)
    return render(request, 'student/ticket_detail.html', {'ticket': ticket})


@login_required
def admin_ticket_list(request):
    if not is_admin(request.user):
        return redirect('dashboard')

    query = request.GET.get('q')
    status_filter = request.GET.get('status')
    tickets = SupportTicket.objects.all().order_by('-created_at')

    if query:
        tickets = tickets.filter(
            Q(subject__icontains=query) |
            Q(description__icontains=query) |
            Q(student__first_name__icontains=query) |
            Q(student__last_name__icontains=query) |
            Q(student__email__icontains=query) |
            Q(ticket_id__icontains=query)
        ).distinct()

    if status_filter:
        tickets = tickets.filter(status=status_filter)

    paginator = Paginator(tickets, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'tickets': page_obj.object_list,
        'query': query,
    }
    return render(request, 'admin/ticket_list.html', context)


@login_required
def resolve_ticket(request, ticket_id):
    """
    View for staff members to change the status of a ticket to 'closed'.
    """
    if not is_admin(request.user):
        messages.error(request, "You do not have permission to perform this action.")
        return redirect('dashboard') # Redirect non-admins

    ticket = get_object_or_404(SupportTicket, ticket_id=ticket_id)

    if request.method == 'POST':
        # Get resolution note from the form
        resolution_note = request.POST.get('resolution_note', '').strip()
        
        # Update ticket details
        ticket.status = 'closed'
        ticket.resolution_note = resolution_note
        ticket.save()

        # --- Get domain and protocol for email links ---
        current_site = get_current_site(request)
        protocol = 'https' if request.is_secure() else 'http'
        domain = current_site.domain
        current_year = timezone.now().year

        # --- Send email notification to student ---
        student_context = {
            'ticket': ticket,
            'student_name': ticket.student.get_full_name() or ticket.student.email, # FIXED
            'current_year': current_year,
            'submit_ticket_url': f"{protocol}://{domain}{reverse('submit_ticket')}", # ADDED
        }
        try:
            send_templated_email(
                'emails/ticket_resolved_notification.html',
                f'Your Support Ticket ({ticket.ticket_id}) Has Been Resolved', # Updated subject
                [ticket.student.email],
                student_context
            )
        except Exception as e:
            print(f"Error sending resolution email for ticket {ticket.ticket_id}: {e}")
            messages.warning(request, f"Ticket {ticket.ticket_id} was resolved, but failed to send notification email.")

        messages.success(request, f"Ticket {ticket.ticket_id} has been resolved and the student notified.")
        return redirect('admin_ticket_list')
    
    messages.error(request, "Invalid request method.")
    return redirect('admin_ticket_list')



@login_required
@user_passes_test(is_admin)
def user_management_view(request):
    """
    Admin view to list all non-superuser accounts for role management.
    """
    query = request.GET.get('q', '')

    # Fetch all users who are NOT superusers
    users_list = User.objects.filter(is_superuser=False).order_by('email')

    if query:
        # Search by name or email
        users_list = users_list.filter(
            Q(email__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        ).distinct()

    # Pagination
    paginator = Paginator(users_list, 15)  
    page_number = request.GET.get('page')
    
    try:
        page_obj = paginator.get_page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    context = {
        'page_obj': page_obj,
        'query': query,
    }
    return render(request, 'admin/user_management.html', context)


@login_required
@user_passes_test(is_admin)
@require_POST
def toggle_user_status(request, pk):
    """
    AJAX endpoint to promote/demote or disable/enable a user.
    """
    user_to_update = get_object_or_404(User, pk=pk)
    field = request.POST.get('field') # e.g., 'is_instructor', 'is_student', 'is_active'
    
    # Security check: Admin cannot change their own active status or superuser status
    if user_to_update == request.user and field == 'is_active':
        return JsonResponse({'success': False, 'error': "You cannot disable your own active status."}, status=403)
    
    # 1. Handle Role Toggle (is_instructor)
    if field == 'is_instructor':
        user_to_update.is_instructor = not user_to_update.is_instructor
        
        # When promoting to instructor, ensure they are NOT staff or student (optional for clarity)
        if user_to_update.is_instructor:
            user_to_update.is_student = False
        else:
            # If demoting, set them back to student by default
            user_to_update.is_student = True 
            
        user_to_update.save()
        
        status = "promoted to Instructor" if user_to_update.is_instructor else "demoted to Student"
        return JsonResponse({'success': True, 'message': f'User {user_to_update.get_full_name()} {status} successfully.'})

    elif field == 'is_active':
        user_to_update.is_active = not user_to_update.is_active
        user_to_update.save()
        
        status = "enabled" if user_to_update.is_active else "disabled"
        return JsonResponse({'success': True, 'message': f'User {user_to_update.get_full_name()} account {status} successfully.'})
    
    return JsonResponse({'success': False, 'error': "Invalid field specified."}, status=400)


@user_passes_test(is_admin)
def group_management_view(request, pk=None):
    if pk:
        group = get_object_or_404(Group, pk=pk)
        title = f"Edit Group: {group.name}"
    else:
        group = None
        title = "Create New Group"

    if request.method == 'POST':
        form = GroupPermissionForm(request.POST, instance=group)
        if form.is_valid():
            form.save()
            messages.success(request, f"Group '{form.cleaned_data['name']}' saved successfully!")
            return redirect('group_list')
    else:
        form = GroupPermissionForm(instance=group)

    context = {
        'form': form,
        'title': title,
        'group': group,
    }
    return render(request, 'admin/group_management.html', context)


@user_passes_test(is_admin)
def group_list_view(request):
    groups = Group.objects.all().order_by('name')
    context = {'groups': groups}
    return render(request, 'admin/group_list.html', context)

@user_passes_test(is_admin)
@require_POST
def group_delete_view(request, pk):
    group = get_object_or_404(Group, pk=pk)
    group_name = group.name
    group.delete()
    messages.success(request, f"Group '{group_name}' was deleted successfully.")
    return redirect('group_list')
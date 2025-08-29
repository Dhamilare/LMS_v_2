from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
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
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.contrib.sites.shortcuts import get_current_site
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from .utils import send_custom_password_reset_email
from django.contrib.auth.forms import PasswordResetForm
from itertools import chain


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
        email_subject = f"New Enrollment for '{course.title}'"
        email_context = {
            'instructor_name': instructor.get_full_name() or instructor.username,
            'student_name': enrollment.student.get_full_name() or enrollment.student.username,            
	    'course_title': course.title,
            'enrollment_date': enrollment.enrolled_at.strftime('%Y-%m-%d'),
        }
        
        send_templated_email(
           'emails/student_enrolled.html',
            email_subject,
            [instructor.email],
            email_context
        )


def custom_password_reset(request):
    if request.method == "POST":
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            users = User.objects.filter(email=email, is_active=True)
            if users.exists():
                for user in users:
                    send_custom_password_reset_email(user, request)
            return redirect('password_reset_done')
            
    else:
        form = PasswordResetForm()

    context = {
        "form": form,
    }
    return render(request, "accounts/password_reset.html", context)


@login_required
def set_password_after_microsoft_login(request):
    """
    Allows a user who has logged in via a social provider to set a local password.
    """
    if request.user.has_usable_password():
        return redirect("dashboard")

    if request.method == "POST":
        # Pass the user instance and POST data correctly
        form = SetPasswordModelForm(data=request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            logout(request)
            messages.success(request, "Your password has been set successfully. Please log in with your new password.")
            return redirect("login")
    else:
        # Pass the user instance for a GET request
        form = SetPasswordModelForm(instance=request.user)

    return render(request, "accounts/set_password.html", {"form": form})


# Helper functions for role-based access control
def is_admin(user):
    return user.is_authenticated and user.is_staff

def is_instructor(user):
    return user.is_authenticated and user.is_instructor

def is_student(user):
    return user.is_authenticated and user.is_student

def is_ajax(request):
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'

# --- Authentication and Dashboard Views ---

def student_register(request):
    """
    Handles student registration with email verification using the existing
    send_templated_email utility function.
    """
    if request.method == 'POST':
        form = StudentRegistrationForm(request.POST)
        if form.is_valid():
            # Save user with is_active=False
            user = form.save(commit=False)
            user.is_active = False
            user.save()

            # Prepare context for the email template
            current_site = get_current_site(request)
            context = {
                'user': user,
                'domain': current_site.domain,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': default_token_generator.make_token(user),
            }

            # Use the custom email utility to send the verification email
            send_templated_email(
                template_name='emails/account_activation_email.html',
                subject='Activate your LMS account',
                recipient_list=[form.cleaned_data.get('email')],
                context=context
            )

            messages.success(request, 'Registration successful! Please check your email to activate your account.')
            return redirect('login')
        else:
            messages.error(request, 'Registration failed. Please correct the errors.')
    else:
        form = StudentRegistrationForm()
    return render(request, 'accounts/register.html', {'form': form})


def verify_email(request, uidb64, token):
    """
    Verifies the email token and activates the user account.
    """
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except(TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        messages.success(request, 'Thank you for your email confirmation. You can now log in to your account.')
        return redirect('login')
    else:
        messages.error(request, 'Activation link is invalid or has expired.')
        return redirect('login')
    

def user_login(request):
    """
    Handles user login for all roles (Admin, Instructor, Student) using email-based auth.
    """
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Welcome back, {user.username}!')
            return redirect('dashboard')
        else:
            messages.error(request, "Email or Password Incorrect!.")
    else:
        form = LoginForm()
    
    return render(request, 'accounts/login.html', {'form': form})

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
        enrolled_paginator = Paginator(enrolled_courses_list, 3) # 6 items per page
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

@login_required
@user_passes_test(is_admin)
def create_instructor(request):
    """
    Allows an Admin to create a new Instructor account.
    """
    if request.method == 'POST':
        form = InstructorCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f'Instructor {user.username} created successfully!')
            return redirect('instructor_list')
        else:
            messages.error(request, 'Failed to create instructor. Please correct the errors.')
    else:
        form = InstructorCreationForm()
    return render(request, 'admin/create_instructor.html', {'form': form})


@login_required
@user_passes_test(is_admin)
def instructor_list(request):
    """
    Admin view to list all instructors with added search and pagination.
    """
    # Get the search query from the GET request, defaulting to an empty string if not present
    query = request.GET.get('q', '')

    # Start with all users who are marked as instructors
    instructors_list = User.objects.filter(is_instructor=True)

    if query:
        # If a search query is provided, filter the instructors using a Q object
        instructors_list = instructors_list.filter(
            Q(username__icontains=query) |
            Q(email__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        )

    # Order the final result by username
    instructors_list = instructors_list.order_by('username')
    
    # --- Pagination Logic ---
    # Set the number of items per page
    paginator = Paginator(instructors_list, 10)  # Show 10 instructors per page
    page = request.GET.get('page')

    try:
        instructors = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        instructors = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        instructors = paginator.page(paginator.num_pages)
    
    # Pass the paginated instructors and the original search query to the template
    return render(request, 'admin/instructor_list.html', {
        'instructors': instructors,
        'query': query
    })



@login_required
@user_passes_test(is_admin)
def instructor_update(request, pk):
    """
    Admin view to update an instructor's details.
    """
    instructor = get_object_or_404(User, pk=pk, is_instructor=True)
    template_name = 'admin/_instructor_form.html'

    if request.method == 'POST':
        form = InstructorUpdateForm(request.POST, instance=instructor)
        if form.is_valid():
            form.save()
            messages.success(request, f'Instructor "{instructor.username}" updated successfully!')
            if is_ajax(request):
                # Return a JSON response for AJAX requests
                return JsonResponse({'success': True, 'message': f'Instructor "{instructor.username}" updated successfully!'})
            return redirect('instructor_list')
        else:
            if is_ajax(request):
                # Return the form HTML and an error message for AJAX validation errors
                form_html = render_to_string(template_name, {'form': form, 'instructor': instructor, 'page_title': f'Edit Instructor: {instructor.username}'}, request=request)
                return JsonResponse({'success': False, 'form_html': form_html, 'error': 'Validation failed. Please correct the errors below.'})
            messages.error(request, 'Failed to update instructor. Please correct the errors.')
    else:
        form = InstructorUpdateForm(instance=instructor)

    # Return the form HTML for the initial GET request (AJAX or not)
    return render(request, template_name, {'form': form, 'instructor': instructor, 'page_title': f'Edit Instructor: {instructor.username}'})


@login_required
@user_passes_test(is_admin)
def instructor_delete(request, pk):
    """
    Admin view to delete an instructor.
    """
    instructor = get_object_or_404(User, pk=pk, is_instructor=True)
    template_name = 'admin/_confirm_delete.html'

    if request.method == 'POST':
        if instructor == request.user: # Prevent admin from deleting themselves
            if is_ajax(request):
                return JsonResponse({'success': False, 'error': "You cannot delete your own account."})
            messages.error(request, "You cannot delete your own account.")
            return redirect('instructor_list')
        
        instructor.delete()
        messages.success(request, f'Instructor "{instructor.username}" deleted successfully.')
        if is_ajax(request):
            # Return a JSON response for AJAX requests
            return JsonResponse({'success': True, 'message': f'Instructor "{instructor.username}" deleted successfully!'})
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
    # 1. Get search query and selected category from request
    search_query = request.GET.get('q', '')
    selected_category = request.GET.get('category', '')

    # 2. Start with the base queryset for courses created by the instructor
    courses = Course.objects.filter(instructor=request.user)

    # 3. Apply the search filter if a query is present
    if search_query:
        courses = courses.filter(
            Q(title__icontains=search_query) | Q(description__icontains=search_query)
        )

    # 4. Apply the category filter if a category is selected
    if selected_category:
        courses = courses.filter(category=selected_category)
        
    # 5. Annotate with enrollment count and order the final queryset
    courses = courses.annotate(
        total_enrollments=Count('enrollments')
    ).order_by('-created_at')

    # 6. Set up pagination with 6 courses per page
    paginator = Paginator(courses, 6)
    page_number = request.GET.get('page')

    try:
        page_obj = paginator.get_page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    # 7. Pass all necessary data to the template context
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'selected_category': selected_category, # The currently selected category value
        'categories': Course.CATEGORY_CHOICES, # The list of all categories
    }

    return render(request, 'instructor/course_list.html', context)

@login_required
def all_courses(request):
    """
    Displays a list of all published courses with comprehensive search and pagination,
    indicating the user's enrollment status for each course.
    """
    # Get the search query from the URL parameters
    search_query = request.GET.get('q', '')

    # Start with all published courses
    courses_list = Course.objects.filter(is_published=True).annotate(average_rating=Avg('ratings__rating')).order_by('title')

    # Apply comprehensive search if a query exists
    if search_query:
        courses_list = courses_list.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(instructor__first_name__icontains=search_query) |
            Q(instructor__last_name__icontains=search_query)
        ).distinct()

    # Get a set of all courses the current user is enrolled in for quick lookups
    enrolled_course_ids = set(Enrollment.objects.filter(student=request.user).values_list('course__id', flat=True))

    completed_course_slugs = set(Enrollment.objects.filter(
        student=request.user, 
        completed=True
    ).values_list('course__slug', flat=True))

    # Prepare a new list of course objects with an `is_enrolled` status
    courses_with_status = []
    for course in courses_list:
        courses_with_status.append({
            'course': course,
            'is_enrolled': course.id in enrolled_course_ids,
            'is_completed': course.slug in completed_course_slugs,
            'average_rating': course.average_rating
        })

    # Set up pagination with 6 courses per page
    paginator = Paginator(courses_with_status, 6)
    page_number = request.GET.get('page')

    try:
        page_obj = paginator.get_page(page_number)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        page_obj = paginator.page(1)
    except EmptyPage:
        # If page is out of range, deliver last page of results.
        page_obj = paginator.page(paginator.num_pages)

    context = {
        'page_obj': page_obj,  # Pass the page object to the template
        'search_query': search_query,
    }
    return render(request, 'student/courses.html', context)


@login_required
@user_passes_test(is_instructor)
def course_create(request):
    """
    Allows an instructor to create a new course.
    """
    template_name = 'instructor/course_form.html' if is_ajax(request) else 'instructor/course_form.html'

    if request.method == 'POST':
        form = CourseForm(request.POST, request.FILES)
        if form.is_valid():
            course = form.save(commit=False)
            course.instructor = request.user
            course.save()
            messages.success(request, f'Course "{course.title}" created successfully!')
            if is_ajax(request):
                return JsonResponse({'success': True, 'message': f'Course "{course.title}" created successfully!', 'redirect_url': str(course.get_absolute_url())}) # Assuming get_absolute_url
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
    Ensures the instructor owns the course.
    """
    course = get_object_or_404(Course, slug=slug, instructor=request.user)
    template_name = 'instructor/_course_form.html' if is_ajax(request) else 'instructor/_course_form.html'

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
    template_name = 'instructor/_confirm_delete.html' if is_ajax(request) else 'instructor/_confirm_delete.html'

    if request.method == 'POST':
        course.delete()
        messages.success(request, f'Course "{course.title}" deleted successfully.')
        if is_ajax(request):
            return JsonResponse({'success': True, 'message': f'Course "{course.title}" deleted successfully!', 'redirect_url': str(redirect('course_list').url)})
        return redirect('course_list')
    
    context = {'object': course, 'type': 'course', 'course_slug': course.slug}
    if is_ajax(request):
        return render(request, template_name, context)
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
            # Check for a passing attempt
            has_passed_final_quiz = StudentQuizAttempt.objects.filter(
                student=request.user,
                quiz=course_quiz,
                passed=True
            ).exists()
            
            # Check if all attempts are used up and all failed
            if course_quiz.max_attempts: # Ensure max_attempts exists on the quiz model
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
        'has_failed_course': has_failed_course, # Add the new variable
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
    Allows an instructor to add a new module to their course.
    """
    course = get_object_or_404(Course, slug=course_slug, instructor=request.user)
    template_name = 'instructor/_module_form.html' if is_ajax(request) else 'instructor/_module_form.html'

    if request.method == 'POST':
        form = ModuleForm(request.POST)
        if form.is_valid():
            module = form.save(commit=False)
            module.course = course
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
    Allows an instructor to update a module in their course.
    """
    course = get_object_or_404(Course, slug=course_slug, instructor=request.user)
    module = get_object_or_404(Module, id=module_id, course=course)
    template_name = 'instructor/_module_form.html' if is_ajax(request) else 'instructor/_module_form.html'

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
    """
    Allows an instructor to delete a module.
    """
    course = get_object_or_404(Course, slug=course_slug, instructor=request.user)
    module = get_object_or_404(Module, id=module_id, course=course)
    template_name = 'instructor/_confirm_delete.html' if is_ajax(request) else 'instructor/_confirm_delete.html'

    if request.method == 'POST':
        module.delete()
        messages.success(request, f'Module "{module.title}" deleted successfully.')
        if is_ajax(request):
            return JsonResponse({'success': True, 'message': f'Module "{module.title}" deleted successfully!'})
        return redirect('course_detail', slug=course.slug)
    
    context = {'object': module, 'type': 'module', 'course_slug': course_slug}
    if is_ajax(request):
        return render(request, template_name, context)
    return render(request, template_name, context)

@login_required
@user_passes_test(is_instructor)
def lesson_create(request, course_slug, module_id):
    """
    Allows an instructor to add a new lesson to a module.
    """
    course = get_object_or_404(Course, slug=course_slug, instructor=request.user)
    module = get_object_or_404(Module, id=module_id, course=course)
    template_name = 'instructor/_lesson_form.html' if is_ajax(request) else 'instructor/_lesson_form.html'

    if request.method == 'POST':
        form = LessonForm(request.POST)
        if form.is_valid():
            lesson = form.save(commit=False)
            lesson.module = module
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
    Allows an instructor to update a lesson.
    """
    course = get_object_or_404(Course, slug=course_slug, instructor=request.user)
    module = get_object_or_404(Module, id=module_id, course=course)
    lesson = get_object_or_404(Lesson, id=lesson_id, module=module)
    template_name = 'instructor/_lesson_form.html' if is_ajax(request) else 'instructor/_lesson_form.html'

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
    """
    Allows an instructor to delete a lesson.
    """
    course = get_object_or_404(Course, slug=course_slug, instructor=request.user)
    module = get_object_or_404(Module, id=module_id, course=course)
    lesson = get_object_or_404(Lesson, id=lesson_id, module=module)
    template_name = 'instructor/_confirm_delete.html' if is_ajax(request) else 'instructor/_confirm_delete.html'

    if request.method == 'POST':
        lesson.delete()
        messages.success(request, f'Lesson "{lesson.title}" deleted successfully.')
        if is_ajax(request):
            return JsonResponse({'success': True, 'message': f'Lesson "{lesson.title}" deleted successfully!'})
        return redirect('course_detail', slug=course.slug)
    
    context = {'object': lesson, 'type': 'lesson', 'course_slug': course_slug, 'module_id': module_id}
    if is_ajax(request):
        return render(request, template_name, context)
    return render(request, template_name, context)

@login_required
@user_passes_test(is_instructor)
def content_create(request, course_slug, module_id, lesson_id):
    """
    Allows an instructor to add new content to a lesson.
    Handles file uploads.
    Automatically sets the 'order' field.
    """
    course = get_object_or_404(Course, slug=course_slug, instructor=request.user)
    module = get_object_or_404(Module, id=module_id, course=course)
    lesson = get_object_or_404(Lesson, id=lesson_id, module=module)
    template_name = 'instructor/_content_form.html' if is_ajax(request) else 'instructor/_content_form.html'

    if request.method == 'POST':
        form = ContentForm(request.POST, request.FILES)
        if form.is_valid():
            content = form.save(commit=False)
            content.lesson = lesson
            
            # --- FIX: Automatically set the order for new content ---
            # Get the maximum existing order for content within this lesson
            max_order = Content.objects.filter(lesson=lesson).aggregate(Max('order'))['order__max']
            # Set the new content's order to max_order + 1, or 1 if no content exists yet
            content.order = (max_order or 0) + 1
            # --- END FIX ---

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
                    'form': form,
                    'lesson': lesson,
                    'module': module,
                    'course': course,
                    'content': content, 
                    'page_title': f'Edit Content: {content.title}'
                }, request=request)
                return JsonResponse({'success': False, 'form_html': form_html, 'error': 'Validation failed.'})
            messages.error(request, 'Failed to update content. Please correct the errors.')
    else:
        form = ContentForm(instance=content)

    return render(request, template_name, {
        'form': form,
        'lesson': lesson,
        'module': module,
        'course': course,
        'content': content, 
        'page_title': f'Edit Content: {content.title}'
    })

@login_required
@user_passes_test(is_instructor)
def content_delete(request, course_slug, module_id, lesson_id, content_id):
    """
    Allows an instructor to delete content.
    """
    course = get_object_or_404(Course, slug=course_slug, instructor=request.user)
    module = get_object_or_404(Module, id=module_id, course=course)
    lesson = get_object_or_404(Lesson, id=lesson_id, module=module)
    content = get_object_or_404(Content, id=content_id, lesson=lesson)
    template_name = 'instructor/_confirm_delete.html' if is_ajax(request) else 'instructor/_confirm_delete.html'

    if request.method == 'POST':
        content.delete()
        messages.success(request, f'Content "{content.title}" deleted successfully.')
        if is_ajax(request):
            return JsonResponse({'success': True, 'message': f'Content "{content.title}" deleted successfully!'})
        return redirect('course_detail', slug=course.slug)
    
    context = {'object': content, 'type': 'content', 'course_slug': course_slug, 'module_id': module_id, 'lesson_id': lesson_id}
    if is_ajax(request):
        return render(request, template_name, context)
    return render(request, template_name, context)


@login_required
def content_detail(request, course_slug, module_id, lesson_id, content_id):
    """
    Displays the content of a specific lesson.
    Students can view published content.
    Instructors can view their own content (published or not).
    """
    course = get_object_or_404(Course, slug=course_slug)
    module = get_object_or_404(Module, id=module_id, course=course)
    lesson = get_object_or_404(Lesson, id=lesson_id, module=module)
    content = get_object_or_404(Content, id=content_id, lesson=lesson)

    student_progress = None
    if request.user.is_authenticated and request.user.is_student:
        # Get or create the progress record for this specific content item
        student_progress, _ = StudentContentProgress.objects.get_or_create(
            student=request.user,
            content=content
        )

    # Determine if the user can access content (instructor of this course OR enrolled student)
    can_view_content_page = False
    quiz_obj = None # Initialize quiz_obj
    if request.user.is_authenticated:
        if request.user.is_instructor and course.instructor == request.user:
            can_view_content_page = True
        elif request.user.is_student and course.is_published and Enrollment.objects.filter(student=request.user, course=course).exists():
            can_view_content_page = True

    if not can_view_content_page:
        messages.error(request, "You do not have permission to view this content.")
        return redirect('dashboard')

    # If content is a quiz, fetch the associated quiz object
    if content.content_type == 'quiz':
        quiz_obj = Quiz.objects.filter(lesson=lesson).first()
        if not quiz_obj:
            messages.warning(request, "This quiz content is not linked to an actual quiz yet.")


    context = {
        'course': course,
        'module': module,
        'lesson': lesson,
        'content': content,
        'student_progress': student_progress,
        'quiz_obj': quiz_obj,
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

            # Always send instructor notification
            send_enrollment_email_to_instructor(request, enrollment)

            # Always send student confirmation email
            email_subject = f"Enrollment Confirmation: {course.title}"
            email_context = {
                'student_name': student.get_full_name() or student.username,
                'course_title': course.title,
                'instructor_name': course.instructor.get_full_name() or course.instructor.username,
                'enrollment_date': enrollment.enrolled_at.strftime('%B %d, %Y'),
                'course_url': request.build_absolute_uri(course.get_absolute_url()),
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
@user_passes_test(is_student) # Only students can mark content as complete
def mark_content_completed(request, course_slug, module_id, lesson_id, content_id):
    """
    Allows a student to mark a content item as completed (or incomplete).
    This is an AJAX endpoint.
    """
    if not is_ajax(request) or request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request.'}, status=400)

    course = get_object_or_404(Course, slug=course_slug)
    module = get_object_or_404(Module, id=module_id, course=course)
    lesson = get_object_or_404(Lesson, id=lesson_id, module=module)
    content = get_object_or_404(Content, id=content_id, lesson=lesson)
    student = request.user

    # Ensure student is enrolled in the course to mark content complete
    if not Enrollment.objects.filter(student=student, course=course).exists():
        return JsonResponse({'success': False, 'error': 'You must be enrolled in this course to mark content.'}, status=403)

    try:
        progress, created = StudentContentProgress.objects.get_or_create(
            student=student,
            content=content,
            defaults={'completed': True, 'completed_at': timezone.now()}
        )
        if not created:
            # Toggle completed status
            progress.completed = not progress.completed
            if progress.completed:
                progress.completed_at = timezone.now()
            else:
                progress.completed_at = None
            progress.save()
        
        status_message = "marked as complete." if progress.completed else "marked as incomplete."
        messages.success(request, f'Content "{content.title}" {status_message}')
        return JsonResponse({'success': True, 'completed': progress.completed, 'message': f'Content {status_message}'})

    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Failed to update progress: {e}'}, status=500)


@login_required
@user_passes_test(is_student)
def quiz_take(request, course_slug):
    """
    Allows a student to take a course-level quiz, paginating through questions
    in a consistent, randomized order.
    """
    # Fetch core objects
    course = get_object_or_404(Course, slug=course_slug)
    quiz = get_object_or_404(Quiz, course=course)
    enrollment = get_object_or_404(Enrollment, student=request.user, course=course)

    # --- Pre-Quiz Checks ---
    if not course.is_published:
        messages.error(request, "This quiz is not currently available.")
        return redirect('course_detail', slug=course.slug)

    if not enrollment.is_content_completed:
        messages.error(request, "You must complete all course content before taking this assessment.")
        return redirect('course_detail', slug=course.slug)

    if not quiz.questions.exists():
        messages.info(request, "This quiz has no questions yet.")
        return redirect('course_detail', slug=course.slug)

    # --- Attempt Limiting Logic ---
    current_attempts_count = StudentQuizAttempt.objects.filter(
        student=request.user,
        quiz=quiz
    ).count()

    if current_attempts_count >= quiz.max_attempts:
        has_passed_quiz = StudentQuizAttempt.objects.filter(
            student=request.user,
            quiz=quiz,
            passed=True
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

    # --- Session-based Randomization and Reset Logic ---
    quiz_order_session_key = f'quiz_questions_order_{quiz.id}'
    quiz_answers_session_key = 'quiz_answers'
    
    # Check if a new attempt is requested or if the quiz order is not in session
    if request.GET.get('new_attempt') or quiz_order_session_key not in request.session:
        random_question_ids = list(quiz.questions.values_list('id', flat=True).order_by('?'))
        request.session[quiz_order_session_key] = random_question_ids
        request.session[quiz_answers_session_key] = {}
        request.session.modified = True
    
    # Retrieve ordered list of question IDs and answers from the session
    ordered_question_ids = request.session.get(quiz_order_session_key, [])
    quiz_answers = request.session.get(quiz_answers_session_key, {})

    # Fetch questions and sort efficiently using a dictionary
    questions = list(Question.objects.filter(id__in=ordered_question_ids))
    order_map = {id: i for i, id in enumerate(ordered_question_ids)}
    questions.sort(key=lambda q: order_map[q.id])

    # Setup pagination
    page_number = request.GET.get('page', 1)
    try:
        page_number = int(page_number)
    except ValueError:
        page_number = 1
        
    paginator = Paginator(questions, 1)
    page_obj = paginator.get_page(page_number)
    current_question = page_obj.object_list[0]

    # --- Form Handling ---
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
    """
    Handles the final submission and grading of a course-level quiz
    using answers stored in the session.
    """
    course = get_object_or_404(Course, slug=course_slug)
    quiz = get_object_or_404(Quiz, course=course)
    enrollment = get_object_or_404(Enrollment, student=request.user, course=course)

    if not course.is_published:
        messages.error(request, "You are not authorized to submit this quiz.")
        return redirect('course_detail', slug=course.slug)

    if not enrollment.is_content_completed:
        messages.error(request, "You must complete all course content before submitting this assessment.")
        return redirect('course_detail', slug=course.slug)

    # Check for max attempts
    current_attempts_count = StudentQuizAttempt.objects.filter(
        student=request.user,
        quiz=quiz
    ).count()

    if current_attempts_count >= quiz.max_attempts:
        messages.error(request, f"You have already reached the maximum number of attempts ({quiz.max_attempts}) for this quiz.")
        last_attempt = StudentQuizAttempt.objects.filter(student=request.user, quiz=quiz).order_by('-attempt_date').first()
        if last_attempt:
            return redirect('quiz_result', course_slug=course.slug, attempt_id=last_attempt.id)
        else:
            return redirect('course_detail', slug=course.slug)

    # Get answers from session
    quiz_answers = request.session.get('quiz_answers', {})
    
    if not quiz_answers:
        messages.error(request, "No answers found. Please try taking the quiz again.")
        return redirect('quiz_take', course_slug=course.slug)

    total_questions = quiz.questions.count()
    correct_answers_count = 0
    student_answers_to_create = []

    with transaction.atomic():
        # Step 1: Create the QuizAttempt object
        attempt = StudentQuizAttempt.objects.create(
            student=request.user,
            quiz=quiz,
            enrollment=enrollment,
            score=0,
            passed=False
        )

        # Step 2: Prepare StudentAnswer objects for bulk creation
        for question_key, chosen_option_ids in quiz_answers.items():
            question_id = int(question_key)
            question = get_object_or_404(Question, id=question_id, quiz=quiz)
            
            is_correct_for_question = False
            
            correct_options = question.options.filter(is_correct=True)
            correct_options_ids_set = set(correct_options.values_list('id', flat=True))

            # Normalize chosen answers to a list for consistent comparison
            if not isinstance(chosen_option_ids, list):
                chosen_option_ids = [chosen_option_ids]

            chosen_options_ids_set = set(int(id) for id in chosen_option_ids if id)
            
            if chosen_options_ids_set == correct_options_ids_set:
                is_correct_for_question = True
            
            if is_correct_for_question:
                correct_answers_count += 1
            
            # Create StudentAnswer object without setting the M2M field yet
            student_answer = StudentAnswer(
                attempt=attempt,
                question=question
            )
            student_answers_to_create.append(student_answer)

        # Bulk create the StudentAnswer objects
        StudentAnswer.objects.bulk_create(student_answers_to_create)

        # Step 3: Now that StudentAnswers exist, set their chosen_options M2M field
        for question_key, chosen_option_ids in quiz_answers.items():
            # Normalize chosen answers to a list again for consistency
            if not isinstance(chosen_option_ids, list):
                chosen_option_ids = [chosen_option_ids]
            
            if chosen_option_ids:
                question_id = int(question_key)
                
                # Fetch the StudentAnswer object that was just created
                student_answer = get_object_or_404(StudentAnswer, attempt=attempt, question_id=question_id)
                
                # Filter for the chosen options
                chosen_options = Option.objects.filter(id__in=chosen_option_ids, question_id=question_id)
                
                # Set the ManyToManyField
                student_answer.chosen_options.set(chosen_options)
        
        # Step 4: Calculate and save the final score
        score_percentage = 0
        if total_questions > 0:
            score_percentage = (correct_answers_count / total_questions) * 100
        
        attempt.score = round(score_percentage, 2)
        attempt.passed = (score_percentage >= quiz.pass_percentage)
        attempt.save()

    # Clear the session data
    if 'quiz_answers' in request.session:
        del request.session['quiz_answers']
    
    messages.success(request, f'Quiz "{quiz.title}" submitted! Your score: {attempt.score:.2f}%')
    return redirect('quiz_result', course_slug=course.slug, attempt_id=attempt.id)


@login_required
@user_passes_test(is_student)
def quiz_result(request, course_slug, attempt_id):
    """
    Displays the result of a student's quiz attempt.
    """
    course = get_object_or_404(Course, slug=course_slug)
    quiz = get_object_or_404(Quiz, course=course)

    # We use Prefetch to fetch all related options and student answers efficiently
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

    # Map student answers by question ID for easy lookup
    student_answers_map = {sa.question_id: sa for sa in attempt.answers.all()}

    for question in quiz.questions.all().order_by('order'):
        student_answer = student_answers_map.get(question.id)
        
        # Get all correct option IDs for this question
        correct_options_ids = set(question.options.filter(is_correct=True).values_list('id', flat=True))

        # Get all chosen option IDs from the ManyToManyField
        chosen_option_ids = set()
        if student_answer:
            chosen_option_ids = set(student_answer.chosen_options.values_list('id', flat=True))

        # Determine the correctness of the chosen options by comparing sets
        # This logic now works for both single and multi-select questions
        is_correct_question = (chosen_option_ids == correct_options_ids)
        
        # Prepare the options for the template
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

    # Remaining attempts logic
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
        
        # --- Send Completion Email (if not already sent or if re-issuing) ---
        # You might want logic here to prevent re-sending if already sent.
        # For simplicity, we'll send it again if they click "Claim" and it exists.
        # Or, just redirect without sending if already claimed.
        # For now, let's just redirect if already claimed and not re-send email.
        if is_ajax(request):
            return JsonResponse({'success': True, 'message': 'Certificate already claimed.', 'redirect_url': str(redirect('view_certificate', certificate_id=certificate.certificate_id).url)})
        return redirect('view_certificate', certificate_id=certificate.certificate_id)


    try:
        with transaction.atomic():
            certificate = Certificate.objects.create(
                student=student,
                course=course,
            )

            # --- PDF Generation Logic ---
            template_path = 'student/certificate_template.html'
            context = {
                'certificate': certificate,
                'student_name': student.get_full_name() or student.username,
                'course_title': course.title,
                'instructor_name': course.instructor.get_full_name() or course.instructor.username,
                'issue_date': certificate.issue_date,
                'certificate_id': certificate.certificate_id,
                'request': request, # Pass request to access build_absolute_uri in template
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
                'student_name': student.get_full_name() or student.username,
                'course_title': course.title,
                'completion_date': certificate.issue_date, # Use certificate issue date as completion date
                'certificate_url': request.build_absolute_uri(certificate.get_absolute_url()), # Link to view certificate online
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
    Displays the certificate of completion for a student, serving the PDF if available.
    """
    certificate = get_object_or_404(Certificate, certificate_id=certificate_id, student=request.user)

    # If a PDF file exists, serve it directly
    if certificate.pdf_file and certificate.pdf_file.name:
        try:
            # Ensure the file exists on disk before trying to open it
            if os.path.exists(certificate.pdf_file.path):
                with open(certificate.pdf_file.path, 'rb') as pdf:
                    response = HttpResponse(pdf.read(), content_type='application/pdf')
                    # Use 'inline' to display in browser, 'attachment' to force download
                    response['Content-Disposition'] = f'inline; filename="{certificate.course.title}_Certificate_{certificate.certificate_id}.pdf"'
                    return response
            else:
                messages.warning(request, "PDF file not found on server. Rendering HTML version.")
                # Fallback to HTML rendering if PDF file is missing
        except Exception as e:
            messages.error(request, f"Error serving PDF: {e}. Rendering HTML version.")
            import traceback
            print(f"Error serving PDF: {e}\n{traceback.format_exc()}")
            # Fallback to HTML rendering on error
    
    # Fallback to rendering HTML template if no PDF or error serving PDF
    context = {
        'certificate': certificate,
        'student_name': certificate.student.get_full_name() or certificate.student.username,
        'course_title': certificate.course.title,
        'instructor_name': certificate.course.instructor.get_full_name() or certificate.course.instructor.username,
        'issue_date': certificate.issue_date,
        'certificate_id': certificate.certificate_id,
        'request': request, # Pass request to access build_absolute_uri in template
    }
    return render(request, 'student/certificate_template.html', context)


@login_required
@user_passes_test(is_student)
def certificate_catalog(request):
    """
    Displays a list of all certificates a student has earned.
    """
    # Fetch all certificates for the currently logged-in student
    student_certificates = Certificate.objects.filter(student=request.user).order_by('-issue_date')

    context = {
        'student_certificates': student_certificates,
    }
    return render(request, 'student/certificate_catalog.html', context)


@login_required
@user_passes_test(is_admin)
def audit_logs(request):
    """
    Provides a comprehensive audit log and reporting dashboard for administrators
    and instructors, including enrollment statistics and course details.
    """

    # --- Overall Statistics ---
    total_courses = Course.objects.count()
    total_enrollments = Enrollment.objects.count()
    total_students = User.objects.filter(is_student=True).count()
    total_completed_enrollments = Enrollment.objects.filter(completed=True).count()
    
    # Count total certificates issued
    total_certificates_issued = Certificate.objects.count()

    # --- Enrollment Distribution (by Course) ---
    enrollment_by_course_data = (
        Course.objects.annotate(
            enroll_count=Coalesce(Count('enrollments'), 0)
        )
        .order_by('-enroll_count')
    )

    course_labels = [course.title for course in enrollment_by_course_data]
    enrollment_counts = [course.enroll_count for course in enrollment_by_course_data]

    # --- Completion Status (Overall) ---
    completion_status_counts = Enrollment.objects.aggregate(
        completed_count=Count('id', filter=Q(completed=True)),
        in_progress_count=Count('id', filter=Q(completed=False)),
    )

    completion_labels = ['Completed', 'In Progress']
    completion_data = [
        completion_status_counts.get('completed_count', 0) or 0,
        completion_status_counts.get('in_progress_count', 0) or 0,
    ]
    
    # --- Assessment Performance (Passed, Failed, Not Attempted) ---
    # We now get the latest quiz attempt for each student
    latest_attempts = StudentQuizAttempt.objects.filter(
        student_id=OuterRef('student_id'),
        quiz_id=OuterRef('quiz_id')
    ).order_by('-attempt_date').values('passed')[:1]

    # Annotate students with their latest attempt result
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
    
    # Corrected method to get all students enrolled in any course with a quiz
    courses_with_quizzes = Course.objects.filter(quiz__isnull=False)
    all_enrolled_students_count = Enrollment.objects.filter(
        course__in=courses_with_quizzes
    ).values('student_id').distinct().count()

    assessments_passed = passed_students
    assessments_failed = failed_students
    # The number of non-attempted students is total enrolled students minus those who have attempted
    assessments_not_attempted = all_enrolled_students_count - (passed_students + failed_students)
    
    assessments_labels = ['Passed', 'Failed', 'Not Attempted']
    assessments_data = [assessments_passed, assessments_failed, assessments_not_attempted]

    # --- Detailed Enrollment Logs ---
    all_enrollments = (
        Enrollment.objects.select_related('course', 'student', 'course__instructor')
        .order_by('-enrolled_at')
    )

    detailed_logs = []
    for enrollment in all_enrollments:
        # Determine certificate status/link
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

        # Determine assessment status
        assessment_status = "No Quiz"
        if hasattr(enrollment.course, 'quiz'):
            has_attempts = StudentQuizAttempt.objects.filter(
                student=enrollment.student,
                quiz=enrollment.course.quiz
            ).exists()
            if has_attempts:
                if enrollment.is_quiz_passed:
                    assessment_status = "Passed"
                else:
                    assessment_status = "Failed"
            else:
                assessment_status = "Not Attempted"
        
        detailed_logs.append({
            'student_first_name': enrollment.student.first_name,
            'student_last_name': enrollment.student.last_name,
            'student_username': enrollment.student.username,
            'student_email': enrollment.student.email,
            'course_title': enrollment.course.title,
            'instructor_name': enrollment.course.instructor.get_full_name() or enrollment.course.instructor.username,
            'enrolled_at': enrollment.enrolled_at.strftime("%b %d, %Y"), # Format for JS
            'completed_at': enrollment.completed_at.strftime("%b %d, %Y") if enrollment.completed_at else 'N/A', # Format for JS
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
    """
    Provides a sample CSV template for quiz question uploads.
    """
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
    """
    Allows an instructor to edit the details of an existing quiz.
    This view is designed to handle both GET (for modal content) and
    POST (for AJAX form submission) requests.
    """
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
    """
    Deletes a quiz via an AJAX POST request.
    """
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
    """
    Handles creation of a new quiz via AJAX modal.
    """
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'

    if request.method == 'POST':
        form = QuizDetailsForm(request.POST)
        if form.is_valid():
            # Save the form but don't commit to the database yet
            quiz = form.save(commit=False)
            # Set the created_by field to the current user
            quiz.created_by = request.user
            # Now save the quiz to the database
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
    if is_ajax:
        return render(request, 'instructor/quiz_create.html', context)
    return render(request, 'instructor/quiz_create.html', context)


@login_required
@user_passes_test(is_instructor)
def quiz_detail_manage(request, quiz_id):
    """
    Displays details of a quiz and allows management of its questions and options.
    Includes pagination and search functionality.
    """
    # Query the database for the quiz, ensuring it belongs to the current user
    quiz = get_object_or_404(Quiz, id=quiz_id, created_by=request.user)
    
    # Start with all questions for the quiz, ordered by 'order'
    questions_list = quiz.questions.all().order_by('order')

    # --- Search Functionality ---
    search_query = request.GET.get('q')
    if search_query:
        questions_list = questions_list.filter(
            Q(text__icontains=search_query) | 
            Q(options__text__icontains=search_query)
        ).distinct()

    # --- Pagination Functionality ---
    paginator = Paginator(questions_list, 10) # Show 10 questions per page
    page = request.GET.get('page')
    
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        page_obj = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
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
    """
    Handles creation of a new question with options for a quiz via AJAX modal.
    """
    quiz = get_object_or_404(Quiz, id=quiz_id, course__instructor=request.user) # Updated lookup
    
    if request.method == 'POST':
        form = QuestionForm(request.POST)
        option_formset = OptionFormSet(request.POST, prefix='options')
        
        if form.is_valid():
            question = form.save(commit=False)
            question.quiz = quiz
            
            option_formset.instance = question # Link formset to the unsaved question for validation
            
            if option_formset.is_valid():
                with transaction.atomic():
                    question.save() # Save the question after formset validation
                    option_formset.save() # Save the options

                return JsonResponse({'success': True, 'message': f'Question "{question.text[:30]}..." added successfully!'})
            else:
                form.option_formset = option_formset # Attach the validated formset back to the form
                html_form = render_to_string('instructor/question_form.html', {'form': form, 'quiz': quiz}, request=request)
                return JsonResponse({'success': False, 'error': 'Please correct the errors in the options.', 'form_html': html_form}, status=400)
        else:
            html_form = render_to_string('instructor/question_form.html', {'form': form, 'quiz': quiz}, request=request)
            return JsonResponse({'success': False, 'error': 'Please correct the errors in the question.', 'form_html': html_form}, status=400)
    else:
        form = QuestionForm()
        form.option_formset = OptionFormSet(prefix='options') # Initialize the formset for GET requests

    context = {'form': form, 'quiz': quiz}
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return render(request, 'instructor/question_form.html', context)
    return render(request, 'instructor/question_form.html', context)


@login_required
@user_passes_test(is_instructor)
def question_update(request, quiz_id, question_id):
    """
    Handles updating an existing question with options for a quiz via AJAX modal.
    """
    quiz = get_object_or_404(Quiz, id=quiz_id, course__instructor=request.user) # Updated lookup
    question = get_object_or_404(Question, id=question_id, quiz=quiz)

    if request.method == 'POST':
        form = QuestionForm(request.POST, instance=question)
        option_formset = OptionFormSet(request.POST, instance=question, prefix='options')

        if form.is_valid():
            option_formset.instance = question # Set formset instance to the question before validation
            
            if option_formset.is_valid():
                with transaction.atomic():
                    form.save() # Save the question
                    option_formset.save() # Save the options

                return JsonResponse({'success': True, 'message': f'Question "{question.text[:30]}..." updated successfully!'})
            else:
                form.option_formset = option_formset # Attach the validated formset back
                html_form = render_to_string('instructor/question_form.html', {'form': form, 'quiz': quiz, 'question': question}, request=request)
                return JsonResponse({'success': False, 'error': 'Please correct the errors in the options.', 'form_html': html_form}, status=400)
        else:
            html_form = render_to_string('instructor/question_form.html', {'form': form, 'quiz': quiz, 'question': question}, request=request)
            return JsonResponse({'success': False, 'error': 'Please correct the errors in the question.', 'form_html': html_form}, status=400)
    else:
        form = QuestionForm(instance=question)
        form.option_formset = OptionFormSet(instance=question, prefix='options')

    context = {'form': form, 'quiz': quiz, 'question': question}
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return render(request, 'instructor/question_form.html', context)
    return render(request, 'instructor/question_form.html', context)


@login_required
@user_passes_test(is_instructor)
def question_delete(request, quiz_id, question_id):
    """
    Handles deletion of a question via AJAX.
    """
    quiz = get_object_or_404(Quiz, id=quiz_id, course__instructor=request.user) # Updated lookup
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
def quiz_assign_to_course(request, quiz_id): # Renamed view
    """
    Assigns an existing quiz to a course taught by the instructor.
    """
    # Ensure the quiz exists and belongs to a course taught by the instructor OR is unassigned
    # If quiz.course is None, it means it's an unassigned quiz.
    quiz = get_object_or_404(Quiz, id=quiz_id)
    
    # Verify instructor ownership if the quiz is already assigned
    if quiz.course and quiz.course.instructor != request.user:
        messages.error(request, "You do not have permission to assign this quiz.")
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    if request.method == 'POST':
        # Pass the instructor_user to the form to filter courses
        form = QuizAssignmentForm(request.POST, instructor_user=request.user)
        if form.is_valid():
            course = form.cleaned_data['course']
            
            # Check if the chosen course already has a quiz
            if hasattr(course, 'quiz') and course.quiz:
                return JsonResponse({'success': False, 'error': f'Course "{course.title}" already has a quiz assigned.'}, status=400)

            # If the quiz was previously assigned to a different course, unassign it first
            if quiz.course:
                # This scenario is less likely with OneToOneField and careful filtering,
                # but good to have a safeguard if logic changes.
                pass # The OneToOneField will handle re-assignment directly

            # Assign the quiz to the selected course
            quiz.course = course
            quiz.save()

            return JsonResponse({'success': True, 'message': f'Quiz "{quiz.title}" assigned to course "{course.title}" successfully!'})
        else:
            html_form = render_to_string('instructor/quiz_assign_form.html', {'form': form, 'quiz': quiz}, request=request)
            return JsonResponse({'success': False, 'error': 'Validation failed.', 'form_html': html_form}, status=400)
    else:
        # For GET request, initialize form with current assignment if any
        initial_data = {}
        if quiz.course:
            initial_data['course'] = quiz.course.id
        
        # Pass the instructor_user to the form to filter courses
        form = QuizAssignmentForm(initial=initial_data, instructor_user=request.user)
    
    context = {'form': form, 'quiz': quiz}
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return render(request, 'instructor/quiz_assign_form.html', context)
    return render(request, 'instructor/quiz_assign_form.html', context) # Fallback


@login_required
@user_passes_test(is_instructor)
def quiz_upload_csv(request, quiz_id):
    """
    Handles uploading questions for a quiz via CSV.
    Expected CSV format:
    question_text,option1,is_correct1,option2,is_correct2,option3,is_correct3,option4,is_correct4
    - is_correct values: True or False (case-insensitive)
    - Each question must have at least one correct option
    - If quiz.allow_multiple_correct is False → exactly one correct option required
    """
    quiz = get_object_or_404(Quiz, id=quiz_id, course__instructor=request.user)

    if request.method == 'POST':
        form = CSVUploadForm(request.POST, request.FILES)

        if not form.is_valid():
            html_form = render_to_string('instructor/quiz_upload_csv.html', {'form': form, 'quiz': quiz}, request=request)
            return JsonResponse({
                'success': False,
                'error': 'Validation failed.',
                'form_errors': form.errors.as_json(),
                'form_html': html_form
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
                # Get the starting order for new questions
                max_order = quiz.questions.aggregate(models.Max('order'))['order__max'] or 0

                # Decode the uploaded file safely
                try:
                    file_data = csv_file.read().decode('utf-8').splitlines()
                except UnicodeDecodeError:
                    return JsonResponse({'success': False, 'error': 'Unable to decode the CSV file. Ensure it is UTF-8 encoded.'}, status=400)

                reader = csv.reader(file_data)
                header = next(reader, None)  # Skip header

                if header is None:
                    raise ValueError('The CSV file is empty.')

                for i, row in enumerate(reader):
                    row_number = i + 2  # Account for header row
                    if len(row) != 9:
                        raise ValueError(f'Row {row_number}: Expected 9 columns, got {len(row)}.')

                    question_text = row[0].strip()
                    if not question_text:
                        raise ValueError(f'Row {row_number}: Question text cannot be empty.')

                    new_question = Question(quiz=quiz, text=question_text, order=max_order + i + 1)
                    questions_buffer.append(new_question)

                    correct_options_count = 0

                    # Parse 4 options
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

                    # Validate correct option count
                    if correct_options_count == 0:
                        raise ValueError(f'Row {row_number}: Each question must have at least one correct option.')

                    if not quiz.allow_multiple_correct and correct_options_count > 1:
                        raise ValueError(f'Row {row_number}: This quiz allows only one correct option, but {correct_options_count} were found.')

                # Bulk create questions (IDs are populated on Django 3.2+ for most DBs)
                questions_buffer = Question.objects.bulk_create(questions_buffer)

                # Prepare options with linked questions
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

    # For GET request → render form
    form = CSVUploadForm()
    context = {'form': form, 'quiz': quiz}
    return render(request, 'instructor/quiz_upload_csv.html', context)


@login_required
@user_passes_test(is_instructor)
def quiz_download_csv_template(request, quiz_id):
    """
    Provides a sample CSV template for quiz question uploads,
    reflecting quiz rules (single or multiple correct answers allowed).
    Format:
    question_text, option1, is_correct1, option2, is_correct2, option3, is_correct3, option4, is_correct4
    """
    quiz = get_object_or_404(Quiz, id=quiz_id, course__instructor=request.user)

    # Create response object with CSV headers
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="quiz_{quiz_id}_questions_template.csv"'

    # Add BOM for Excel compatibility
    response.write('\ufeff'.encode('utf-8'))

    writer = csv.writer(response)

    # Header row
    writer.writerow([
        'question_text',
        'option1', 'is_correct1',
        'option2', 'is_correct2',
        'option3', 'is_correct3',
        'option4', 'is_correct4'
    ])

    # Instruction row
    if quiz.allow_multiple_correct:
        note = "Example: Multiple correct answers allowed (use True/False, case-insensitive)"
        sample_question = [
            'Which of the following are programming languages?',
            'Python', 'True',
            'HTML', 'False',
            'Java', 'True',
            'CSS', 'False'
        ]
    else:
        note = "Example: Only one correct answer allowed (use True for correct, False for others)"
        sample_question = [
            'What is the capital of France?',
            'Paris', 'True',
            'London', 'False',
            'Berlin', 'False',
            'Rome', 'False'
        ]

    # Write the note as a comment row
    writer.writerow([note] + [''] * 7)

    # Write sample row
    writer.writerow(sample_question)

    return response


@login_required
@user_passes_test(is_student)
def course_transcript(request, course_slug):
    """
    Displays a transcript of all quiz results for a student in a specific course.
    Adds a button to view the transcript if the student has passed the final course quiz.
    """
    course = get_object_or_404(Course, slug=course_slug)
    enrollment = get_object_or_404(Enrollment, student=request.user, course=course)

    # Directly access the final quiz using the OneToOne relationship
    final_quiz = None
    has_passed_final_quiz = False
    
    if hasattr(course, 'quiz'):
        final_quiz = course.quiz
        # Check for a passing attempt on this specific final quiz
        has_passed_final_quiz = StudentQuizAttempt.objects.filter(
            student=request.user,
            quiz=final_quiz,
            passed=True
        ).exists()

    # Fetch all quiz attempts for the student in this course
    course_quizzes = Quiz.objects.filter(course=course)
    attempts = StudentQuizAttempt.objects.filter(
        student=request.user,
        quiz__in=course_quizzes
    ).order_by('attempt_date')

    # Calculate the overall average score for all attempts in the course
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
    Handles assigning a course to a student.

    Sends:
    - Email to the student (they’ve been assigned a course)
    - Email to the instructor who assigned it (confirmation)
    """
    if request.method == 'POST':
        form = AssignCourseForm(request.POST)
        if form.is_valid():
            # Use 'completed' field as per your Enrollment model
            enrollment, created = Enrollment.objects.get_or_create(
                student=form.cleaned_data['student'], 
                course=form.cleaned_data['course'],
                defaults={'completed': False}
            )

            # Check if the enrollment already existed and was completed
            if not created and enrollment.completed:
                return JsonResponse({'success': False, 'message': 'Student is already enrolled in this course.'}, status=400)
            
            # If the enrollment was just created or was not yet completed, proceed
            if created or not enrollment.completed:
                student = enrollment.student
                course = enrollment.course
                assigner = request.user  # current logged-in instructor

                # Email to student
                student_context = {
                    'student_name': student.get_full_name() or student.username,
                    'course_title': course.title,
                    'course_url': request.build_absolute_uri(course.get_absolute_url()),
                    'assigned_by': assigner.get_full_name() or assigner.username,
                }
                send_templated_email(
                    'emails/course_assigned.html',
                    'You have been assigned a new course!',
                    [student.email],
                    student_context
                )

                # Email to instructor (assigner)
                instructor_context = {
                    'instructor_name': assigner.get_full_name() or assigner.username,
                    'student_name': student.get_full_name() or student.username,
                    'course_title': course.title,
                    'assignment_date': timezone.now().strftime('%B %d, %Y'),
                    'course_url': request.build_absolute_uri(course.get_absolute_url()),
                }
                send_templated_email(
                    'emails/course_assigned_confirmation.html',
                    f"Course '{course.title}' successfully assigned!",
                    [assigner.email],
                    instructor_context
                )

                return JsonResponse({'success': True, 'message': f"Course '{course.title}' assigned to {student.get_full_name()} and confirmation sent to you."})
            
            return JsonResponse({'success': False, 'message': 'An unexpected error occurred.'}, status=400)

        else:
            return JsonResponse({'success': False, 'message': 'Validation failed.'}, status=400)
    else:  # GET request
        form = AssignCourseForm()
        return render(request, 'instructor/student_assign_form.html', {'form': form})


@user_passes_test(is_instructor)
def assign_course_page_view(request):
    """
    Renders the main page for assigning courses with a list of all enrollments.
    Includes search, pagination, and a bar chart for progress per student across modules.
    """
    # Use select_related to pre-fetch 'student' and 'course' objects
    all_enrollments = Enrollment.objects.filter(
        course__instructor=request.user
    ).select_related('student', 'course').order_by('-enrolled_at')

    search_query = request.GET.get('q', '')
    if search_query:
        all_enrollments = all_enrollments.filter(
            Q(student__first_name__icontains=search_query) |
            Q(student__last_name__icontains=search_query) |
            Q(student__username__icontains=search_query) |
            Q(course__title__icontains=search_query)
        )

    # --- Data Generation for Bar Chart ---
    chart_labels = []
    chart_datasets = []

    def get_random_color():
        r = random.randint(0, 255)
        g = random.randint(0, 255)
        b = random.randint(0, 255)
        return f'rgba({r}, {g}, {b}, 0.8)'
    
    # Get a list of unique courses for which there are enrollments
    enrolled_courses = {enrollment.course for enrollment in all_enrollments}

    # Get all unique modules for these enrolled courses
    all_modules = Module.objects.filter(
        course__in=enrolled_courses
    ).order_by('title').distinct()

    # Create a map to store the total number of content items per module
    module_content_counts = {
        module.id: Content.objects.filter(lesson__module=module).count()
        for module in all_modules
    }
    
    # Populate chart labels with student names
    enrollment_list = list(all_enrollments)
    for enrollment in enrollment_list:
        student_name = enrollment.student.get_full_name() or enrollment.student.username
        chart_labels.append(student_name)

    # Create a dataset for each unique module
    for module in all_modules:
        module_progress_data = []
        total_content_in_module = module_content_counts.get(module.id, 0)
        
        # Calculate progress for each student for the current module
        for enrollment in enrollment_list:
            student_progress_count = None  # Use None for modules not in the student's course
            
            # Only calculate progress if the module belongs to the student's enrolled course
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
        chart_data = {
            'labels': ['No Students'],
            'datasets': [{
                'label': 'Progress',
                'data': [0],
                'backgroundColor': ['#9CA3AF']
            }]
        }
    else:
        chart_data = {
            'labels': chart_labels,
            'datasets': chart_datasets
        }
    
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
    """
    A view to display a list of all students with pagination and search functionality,
    accessible only to admin users.
    """
    # Get all users who are not superusers
    all_students = User.objects.filter(is_student=True).order_by('date_joined')
    
    # Handle the search query
    query = request.GET.get('q')
    if query:
        # Use Q objects for a comprehensive search across multiple fields
        all_students = all_students.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query)
        ).distinct()

    # Set up pagination
    paginator = Paginator(all_students, 10) 
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'total_students': all_students.count(), # Count the total number of students
        'query': query, # Pass the search query back to the template
    }
    
    return render(request, 'admin/student_list.html', context)


@login_required
def submit_ticket(request):
    """
    View for students to submit a new support ticket.
    """
    if request.method == 'POST':
        form = SupportTicketForm(request.POST)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.student = request.user
            ticket.save()

            # --- Send confirmation email to student ---
            student_context = {
                'ticket': ticket,
                'username': request.user.get_full_name(),
                'current_year': timezone.now().year,
            }
            send_templated_email(
                'emails/ticket_confirmation.html',
                f'Confirmation: Support Request #{ticket.ticket_id}',
                [request.user.email],
                student_context
            )

            # --- Send notification email to admin(s) ---
            # Get all users who are staff members and collect their emails
            admin_users = User.objects.filter(is_staff=True, is_active=True).values_list('email', flat=True)
            admin_emails = [email for email in admin_users if email]
            
            if admin_emails:
                admin_context = {
                    'ticket': ticket,
                    'current_year': timezone.now().year,
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

    context = {
        'page_obj': page_obj,
        'query': query,
    }
    
    return render(request, 'student/ticket_list.html', context)


@login_required
def ticket_detail(request, ticket_id):
    # Ensures only the student who owns the ticket can view it.
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
            Q(student__username__icontains=query) |
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
        return redirect('ticket_list')

    ticket = get_object_or_404(SupportTicket, ticket_id=ticket_id)

    if request.method == 'POST':
        # Get resolution note from the form
        resolution_note = request.POST.get('resolution_note', '').strip()
        
        # Update ticket details
        ticket.status = 'closed'
        ticket.resolution_note = resolution_note
        ticket.save()

        # --- Send email notification to student ---
        student_context = {
            'ticket': ticket,
            'username': ticket.student.get_full_name(),
            'current_year': timezone.now().year,
        }
        try:
            send_templated_email(
                'emails/ticket_resolved_notification.html',
                f'Ticket {ticket.ticket_id} Resolved',
                [ticket.student.email],
                student_context
            )
        except Exception as e:
            print(f"Error sending resolution email: {e}")

    return redirect('admin_ticket_list')



@user_passes_test(is_admin)
def group_management_view(request, pk=None):
    """
    A view to manage group permissions and members.
    Handles both creating a new group and editing an existing one.
    This view is now restricted to staff members.
    """
    if pk:
        # This part handles the 'update' functionality
        group = get_object_or_404(Group, pk=pk)
        title = f"Edit Group: {group.name}"
    else:
        # This part handles the 'create' functionality
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
        'group': group, # Pass the group object to the template
    }
    return render(request, 'admin/group_management.html', context)

@user_passes_test(is_admin)
def group_list_view(request):
    """
    A simple view to list all existing groups.
    This view is also restricted to staff members.
    """
    groups = Group.objects.all().order_by('name')
    context = {
        'groups': groups,
    }
    return render(request, 'admin/group_list.html', context)


@user_passes_test(is_admin)
def group_delete_view(request, pk):
    """
    Deletes a group.
    This view only accepts POST requests and is restricted to staff members.
    """
    group = get_object_or_404(Group, pk=pk)
    group_name = group.name
    group.delete()
    messages.success(request, f"Group '{group_name}' was deleted successfully.")
    return redirect('group_list')
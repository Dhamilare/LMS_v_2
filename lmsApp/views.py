# instructor/views.py (Updated for AJAX Modals)
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string, get_template
from django.db.models import Q, Max, Count, Sum
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
import json

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
    Handles student registration.
    Only allows students to register.
    """
    if request.method == 'POST':
        form = StudentRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user) # Log in the user after successful registration
            messages.success(request, 'Registration successful! Welcome to LMS Portal.')
            return redirect('dashboard')
        else:
            messages.error(request, 'Registration failed. Please correct the errors.')
    else:
        form = StudentRegistrationForm()
    return render(request, 'accounts/register.html', {'form': form})

def user_login(request):
    """
    Handles user login for all roles (Admin, Instructor, Student).
    """
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'Welcome back, {user.username}!')
                return redirect('dashboard')
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Please correct the errors in the form.")
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

    if user.is_instructor:
        # For instructors, fetch their courses.
        # Pagination for instructor courses can be added here if needed.
        context['courses'] = Course.objects.filter(instructor=user).order_by('-created_at')
    elif user.is_student:
        # --- Enrolled Courses Logic ---
        # The progress_percentage, completed, has_certificate, certificate_obj,
        # and can_claim_certificate are now properties on the Enrollment model.
        # We just need to fetch the Enrollment objects.
        enrolled_courses_list = Enrollment.objects.filter(student=user).select_related('course').order_by('-enrolled_at')
        
        # Apply pagination for enrolled courses
        enrolled_paginator = Paginator(enrolled_courses_list, 6) # 6 items per page
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
    Admin view to list all instructors.
    """
    instructors = User.objects.filter(is_instructor=True).order_by('username')
    return render(request, 'admin/instructor_list.html', {'instructors': instructors})

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
    Lists courses managed by the logged-in instructor, with comprehensive search and pagination.
    """
    # Start with courses created by the logged-in instructor
    courses_list = Course.objects.filter(instructor=request.user).order_by('-created_at')
    
    search_query = request.GET.get('q', '')

    if search_query:
        # Filter courses by title or description (case-insensitive)
        courses_list = courses_list.filter(
            Q(title__icontains=search_query) | Q(description__icontains=search_query)
        ).distinct() # Use distinct to avoid duplicate results if a course matches both title and description

    # Set up pagination with 6 courses per page
    paginator = Paginator(courses_list, 6) # 6 courses per page
    page_number = request.GET.get('page')

    try:
        page_obj = paginator.get_page(page_number)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        page_obj = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        page_obj = paginator.page(paginator.num_pages)

    context = {
        'page_obj': page_obj,  # Pass the page object to the template
        'search_query': search_query, # Pass the search query back for the input field
    }
    return render(request, 'instructor/course_list.html', context)


@login_required
def all_courses(request):
    """
    Displays a list of all published courses with comprehensive search and pagination.
    """
    # Get the search query from the URL parameters
    search_query = request.GET.get('q', '')

    # Start with all published courses
    courses_list = Course.objects.filter(is_published=True)

    # Apply comprehensive search if a query exists
    if search_query:
        # Use Q objects to perform a case-insensitive search across multiple fields
        courses_list = courses_list.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(instructor__first_name__icontains=search_query) |
            Q(instructor__last_name__icontains=search_query)
        ).distinct()

    # Set up pagination with 9 courses per page
    paginator = Paginator(courses_list, 6)
    page_number = request.GET.get('page')

    try:
        page_obj = paginator.get_page(page_number)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        page_obj = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
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
    """
    Displays the details of a specific course.
    Allows instructors to manage modules/lessons/content.
    Allows students to view published courses and enroll.
    """
    course = get_object_or_404(Course, slug=slug)
    is_enrolled = False
    modules = course.modules.prefetch_related('lessons__contents').all()

    if request.user.is_authenticated and request.user.is_student:
        is_enrolled = Enrollment.objects.filter(student=request.user, course=course).exists()
        
        student_progress_map = {
            p['content_id']: p['completed']
            for p in StudentContentProgress.objects.filter(
                student=request.user,
                content__lesson__module__course=course
            ).values('content_id', 'completed')
        }

        for module in modules: # Iterate over the pre-fetched modules
            for lesson in module.lessons.all(): # These lessons are also pre-fetched
                all_contents_in_lesson = list(lesson.contents.all()) # Convert to list to ensure consistent iteration
                total_lesson_contents = len(all_contents_in_lesson)
                
                completed_lesson_contents = 0
                for content_item in all_contents_in_lesson:
                    # Check if this specific content item is completed by the student
                    content_item.is_completed = student_progress_map.get(content_item.id, False)
                    if content_item.is_completed:
                        completed_lesson_contents += 1
                
                # A lesson is considered completed if it has content AND all its content is completed.
                # If a lesson has no content, it's not "completed" in terms of student progress.
                lesson.is_completed = (total_lesson_contents > 0 and completed_lesson_contents == total_lesson_contents)

    # Determine if the user can access content (instructor of this course OR enrolled student)
    can_access_content = False
    if request.user.is_authenticated:
        if request.user.is_instructor and course.instructor == request.user:
            can_access_content = True
        elif request.user.is_student and course.is_published and is_enrolled:
            can_access_content = True

    # Access control for viewing the course detail page itself
    if request.user.is_instructor and course.instructor != request.user:
        messages.error(request, "You do not have permission to view this course.")
        return redirect('dashboard')
    elif request.user.is_student and not course.is_published and not is_enrolled:
        messages.error(request, "This course is not yet published or you are not enrolled.")
        return redirect('dashboard')

    context = {
        'course': course,
        'is_enrolled': is_enrolled,
        'can_access_content': can_access_content,
        'modules': modules, # Pass the pre-fetched modules to the template
    }
    return render(request, 'course_detail.html', context)

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
    template_name = 'instructor/_content_form.html' if is_ajax(request) else 'instructor/_content_form.html'

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
                form_html = render_to_string(template_name, {'form': form, 'lesson': lesson, 'module': module, 'course': course, 'page_title': f'Edit Content: {content.title}'}, request=request)
                return JsonResponse({'success': False, 'form_html': form_html, 'error': 'Validation failed.'})
            messages.error(request, 'Failed to update content. Please correct the errors.')
    else:
        form = ContentForm(instance=content)
    return render(request, template_name, {'form': form, 'lesson': lesson, 'module': module, 'course': course, 'page_title': f'Edit Content: {content.title}'})

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
@user_passes_test(is_student) # Only students can enroll
def enroll_course(request, slug):
    """
    Allows a student to enroll in a course.
    """
    course = get_object_or_404(Course, slug=slug)
    student = request.user

    if not course.is_published:
        if is_ajax(request):
            return JsonResponse({'success': False, 'error': 'Cannot enroll in an unpublished course.'}, status=400)
        messages.error(request, 'Cannot enroll in an unpublished course.')
        return redirect('course_detail', slug=course.slug)

    if Enrollment.objects.filter(student=student, course=course).exists():
        if is_ajax(request):
            return JsonResponse({'success': False, 'error': 'You are already enrolled in this course.'}, status=400)
        messages.info(request, 'You are already enrolled in this course.')
        return redirect('course_detail', slug=course.slug)

    try:
        with transaction.atomic():
            enrollment = Enrollment.objects.create(student=student, course=course)
            messages.success(request, f'Successfully enrolled in "{course.title}"!')

            # --- Send Enrollment Confirmation Email ---
            email_subject = f"Enrollment Confirmation: {course.title}"
            email_context = {
                'student_name': student.get_full_name() or student.username,
                'course_title': course.title,
                'instructor_name': course.instructor.get_full_name() or course.instructor.username,
                'enrollment_date': enrollment.enrolled_at,
                'course_url': request.build_absolute_uri(course.get_absolute_url()),
            }
            send_templated_email(
                'emails/enrollment_confirmation.html',
                email_subject,
                [student.email],
                email_context
            )
            # --- End Email Send ---

            if is_ajax(request):
                return JsonResponse({'success': True, 'message': f'Successfully enrolled in "{course.title}"!', 'redirect_url': str(redirect('course_detail', slug=course.slug).url)})
            return redirect('course_detail', slug=course.slug)
    except Exception as e:
        messages.error(request, f'Failed to enroll in course: {e}')
        traceback.print_exc() # Print full traceback to console
        if is_ajax(request):
            return JsonResponse({'success': False, 'error': f'Failed to enroll in course: {e}'}, status=500)
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
        return JsonResponse({'success': True, 'completed': progress.completed, 'message': f'Content "{content.title}" {status_message}'})

    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Failed to update progress: {e}'}, status=500)


@login_required
@user_passes_test(is_student)
def quiz_take(request, course_slug, module_id, lesson_id, content_id):
    """
    Allows a student to take a quiz.
    """
    course = get_object_or_404(Course, slug=course_slug)
    module = get_object_or_404(Module, id=module_id, course=course)
    lesson = get_object_or_404(Lesson, id=lesson_id, module=module)
    content = get_object_or_404(Content, id=content_id, lesson=lesson, content_type='quiz')
    quiz = get_object_or_404(Quiz, lesson=lesson) # Assuming one quiz per lesson for now

    # Access control: Student must be enrolled and course published
    if not Enrollment.objects.filter(student=request.user, course=course).exists() or not course.is_published:
        messages.error(request, "You are not authorized to take this quiz.")
        return redirect('course_detail', slug=course.slug)

    # Check if quiz has questions
    if not quiz.questions.exists():
        messages.info(request, "This quiz has no questions yet.")
        return redirect('content_detail', course_slug=course.slug, module_id=module.id, lesson_id=lesson.id, content_id=content.id)

    form = QuizForm(quiz=quiz) # Initialize form with the quiz instance

    context = {
        'course': course,
        'module': module,
        'lesson': lesson,
        'content': content,
        'quiz': quiz,
        'form': form,
    }
    return render(request, 'student/quiz_take.html', context)

@login_required
@user_passes_test(is_student)
def quiz_submit(request, course_slug, module_id, lesson_id, content_id):
    """
    Handles the submission and grading of a quiz.
    """
    course = get_object_or_404(Course, slug=course_slug)
    module = get_object_or_404(Module, id=module_id, course=course)
    lesson = get_object_or_404(Lesson, id=lesson_id, module=module)
    content = get_object_or_404(Content, id=content_id, lesson=lesson, content_type='quiz')
    quiz = get_object_or_404(Quiz, lesson=lesson)

    # Access control: Student must be enrolled and course published
    if not Enrollment.objects.filter(student=request.user, course=course).exists() or not course.is_published:
        messages.error(request, "You are not authorized to submit this quiz.")
        return redirect('course_detail', slug=course.slug)

    if request.method == 'POST':
        form = QuizForm(request.POST, quiz=quiz)
        if form.is_valid():
            total_questions = quiz.questions.count()
            correct_answers_count = 0
            student_answers_to_save = []

            with transaction.atomic():
                # Create a new quiz attempt record
                attempt = StudentQuizAttempt.objects.create(
                    student=request.user,
                    quiz=quiz,
                    score=0, # Will update later
                    passed=False
                )

                for question in quiz.questions.all():
                    field_name = f'question_{question.id}'
                    chosen_option_id = form.cleaned_data.get(field_name)

                    chosen_option = None
                    if chosen_option_id:
                        chosen_option = get_object_or_404(Option, id=chosen_option_id, question=question)

                    # Save student's answer
                    student_answers_to_save.append(
                        StudentAnswer(
                            attempt=attempt,
                            question=question,
                            chosen_option=chosen_option
                        )
                    )

                    # Check if the chosen option is correct
                    if chosen_option and chosen_option.is_correct:
                        correct_answers_count += 1
                
                # Bulk create student answers
                StudentAnswer.objects.bulk_create(student_answers_to_save)

                # Calculate score
                score_percentage = 0
                if total_questions > 0:
                    score_percentage = (correct_answers_count / total_questions) * 100
                
                # Update the attempt with score and pass/fail status
                attempt.score = round(score_percentage, 2)
                attempt.passed = (score_percentage >= quiz.pass_percentage)
                attempt.save()

                messages.success(request, f'Quiz "{quiz.title}" submitted! Your score: {attempt.score:.2f}%')
                return redirect('quiz_result', course_slug=course.slug, module_id=module.id, lesson_id=lesson.id, content_id=content.id, attempt_id=attempt.id)
        else:
            # If form is not valid, re-render the quiz_take page with errors
            messages.error(request, "Please correct the errors below.")
            context = {
                'course': course,
                'module': module,
                'lesson': lesson,
                'content': content,
                'quiz': quiz,
                'form': form,
            }
            return render(request, 'student/quiz_take.html', context)
    else:
        messages.error(request, "Invalid request method for quiz submission.")
        return redirect('quiz_take', course_slug=course.slug, module_id=module.id, lesson_id=lesson.id, content_id=content.id)

@login_required
@user_passes_test(is_student)
def quiz_result(request, course_slug, module_id, lesson_id, content_id, attempt_id):
    """
    Displays the result of a student's quiz attempt.
    """
    course = get_object_or_404(Course, slug=course_slug)
    module = get_object_or_404(Module, id=module_id, course=course)
    lesson = get_object_or_404(Lesson, id=lesson_id, module=module)
    content = get_object_or_404(Content, id=content_id, lesson=lesson, content_type='quiz')
    quiz = get_object_or_404(Quiz, lesson=lesson)
    attempt = get_object_or_404(StudentQuizAttempt, id=attempt_id, student=request.user, quiz=quiz)

    # Access control: Student must be enrolled and course published
    if not Enrollment.objects.filter(student=request.user, course=course).exists() or not course.is_published:
        messages.error(request, "You are not authorized to view this quiz result.")
        return redirect('course_detail', slug=course.slug)

    # Fetch all questions and their options for the quiz
    questions_with_answers = []
    for question in quiz.questions.all().order_by('order'):
        options = list(question.options.all())
        student_answer = StudentAnswer.objects.filter(attempt=attempt, question=question).first()
        
        chosen_option_id = student_answer.chosen_option.id if student_answer and student_answer.chosen_option else None
        
        questions_with_answers.append({
            'question': question,
            'options': options,
            'chosen_option_id': chosen_option_id,
            'is_correct': student_answer.chosen_option.is_correct if student_answer and student_answer.chosen_option else False,
            'correct_option': next((opt for opt in options if opt.is_correct), None)
        })

    context = {
        'course': course,
        'module': module,
        'lesson': lesson,
        'content': content,
        'quiz': quiz,
        'attempt': attempt,
        'questions_with_answers': questions_with_answers,
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
    total_students = User.objects.filter(is_student=True).count() # Count actual student users
    total_completed_enrollments = Enrollment.objects.filter(completed=True).count()

    # --- Data for Enrollment Distribution Pie Chart (by Course) ---
    # Get enrollment counts per course
    enrollment_by_course_data = Course.objects.annotate(
        enroll_count=Coalesce(Count('enrollments'), 0) # Use 'enrollments' related_name
    ).order_by('-enroll_count')

    course_labels = [course.title for course in enrollment_by_course_data]
    enrollment_counts = [course.enroll_count for course in enrollment_by_course_data]

    # --- Data for Completion Status Pie Chart (Overall) ---
    # Get counts of completed vs. in-progress enrollments
    completion_status_counts = Enrollment.objects.aggregate(
        completed_count=Count('id', filter=Q(completed=True)),
        in_progress_count=Count('id', filter=Q(completed=False))
    )
    completion_labels = ['Completed', 'In Progress']
    completion_data = [
        completion_status_counts['completed_count'],
        completion_status_counts['in_progress_count']
    ]

    # --- Detailed Enrollment Logs ---
    # Fetch all enrollments with related course, student, and instructor info
    # The certificate_obj, has_certificate, progress_percentage are now @properties on Enrollment model
    all_enrollments = Enrollment.objects.select_related(
        'course', 'student', 'course__instructor'
    ).order_by('-enrolled_at')

    detailed_logs = []
    for enrollment in all_enrollments:
        certificate_status = "N/A"
        certificate_link = "#"
        
        if enrollment.has_certificate:
            certificate_status = "Issued"
            certificate_link = enrollment.certificate_obj.get_absolute_url() # Use the model's get_absolute_url
        elif enrollment.can_claim_certificate: # Check if eligible but not yet claimed
            certificate_status = "Eligible (Claimable)"
        elif enrollment.completed: # Completed but not eligible/claimed (e.g., if no certificate defined)
            certificate_status = "Completed (No Certificate)"


        detailed_logs.append({
            'student_first_name': enrollment.student.first_name, # Added
            'student_last_name': enrollment.student.last_name,   # Added
            'student_username': enrollment.student.username,
            'student_email': enrollment.student.email,
            'course_title': enrollment.course.title,
            'instructor_name': enrollment.course.instructor.get_full_name() or enrollment.course.instructor.username,
            'enrolled_at': enrollment.enrolled_at,
            'completed_at': enrollment.completed_at, # Now directly from the model
            'is_completed': enrollment.completed,
            'progress_percentage': enrollment.progress_percentage, # Now directly from the model property
            'certificate_status': certificate_status,
            'certificate_link': certificate_link,
        })

    context = {
        'total_courses': total_courses,
        'total_enrollments': total_enrollments,
        'total_students': total_students,
        'total_completed_enrollments': total_completed_enrollments,
        'course_labels_json': json.dumps(course_labels),
        'enrollment_counts_json': json.dumps(enrollment_counts),
        'completion_labels_json': json.dumps(completion_labels),
        'completion_data_json': json.dumps(completion_data),
        'detailed_logs': detailed_logs,
    }
    return render(request, 'admin/reporting.html', context)
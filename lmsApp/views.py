from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Avg
from .forms import *
from .models import *
from django.db import transaction

# --- Security Decorators ---
def role_required(role):
    """A decorator to restrict access to views based on user role."""
    def decorator(view_func):
        def wrapper_func(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            if request.user.role == role:
                return view_func(request, *args, **kwargs)
            else:
                messages.error(request, "You do not have permission to access this page.")
                return redirect('dashboard')
        return wrapper_func
    return decorator

# --- Authentication Views ---
def register_view(request):
    """View for user registration."""
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            user.role = User.Role.STUDENT
            user.save()
            login(request, user)
            messages.success(request, "Registration successful. Welcome!")
            return redirect('student_dashboard')
        else:
            for error in form.errors.values():
                messages.error(request, error)
    else:
        form = CustomUserCreationForm()
    return render(request, 'accounts/register.html', {'form': form})

def login_view(request):
    """View for user login."""
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f"Welcome back, {user.username}!")
                return redirect('dashboard')
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = CustomAuthenticationForm()
    return render(request, 'accounts/login.html', {'form': form})

@login_required
def logout_view(request):
    """View to log out the user."""
    logout(request)
    messages.info(request, "You have been logged out successfully.")
    return redirect('login')

@login_required
def dashboard_view(request):
    """Redirects authenticated users to their specific dashboard based on role."""
    if request.user.role == User.Role.STUDENT:
        return redirect('student_dashboard')
    elif request.user.role == User.Role.INSTRUCTOR:
        return redirect('instructor_dashboard')
    elif request.user.role == User.Role.ADMIN:
        return redirect('moderator_dashboard')
    else:
        messages.warning(request, "Your account has an invalid role.")
        return redirect('logout')


# --- Student Views ---
@login_required
@role_required(User.Role.STUDENT)
def student_dashboard(request):
    """Student dashboard view."""
    enrolled_courses = Enrollment.objects.filter(student=request.user).select_related('course')
    notifications = Notification.objects.filter(user=request.user, is_read=False)[:5]
    context = {
        'enrolled_courses': enrolled_courses,
        'notifications': notifications,
    }
    return render(request, 'student/dashboard.html', context)

@login_required
@role_required(User.Role.STUDENT)
def my_courses(request):
    """View for a student to see all their enrolled courses."""
    enrolled_courses = Enrollment.objects.filter(student=request.user).select_related('course')
    context = {'enrolled_courses': enrolled_courses}
    return render(request, 'student/my_courses.html', context)

@login_required
@role_required(User.Role.STUDENT)
def course_detail(request, course_id):
    """Detailed view of a single course."""
    course = get_object_or_404(Course, pk=course_id)
    # Check if the student is enrolled in the course.
    if not Enrollment.objects.filter(student=request.user, course=course).exists():
        messages.error(request, "You are not enrolled in this course.")
        return redirect('my_courses')
    
    lessons = course.lessons.all()
    assignments = course.assignments.all()
    quizzes = course.quizzes.all()

    context = {
        'course': course,
        'lessons': lessons,
        'assignments': assignments,
        'quizzes': quizzes,
    }
    return render(request, 'student/course_detail.html', context)

@login_required
@role_required(User.Role.STUDENT)
def lesson_detail(request, lesson_id):
    """View for a single lesson."""
    lesson = get_object_or_404(Lesson, pk=lesson_id)
    # Security check: ensure student is enrolled in the course
    if not Enrollment.objects.filter(student=request.user, course=lesson.course).exists():
        messages.error(request, "You do not have access to this lesson.")
        return redirect('my_courses')
        
    context = {'lesson': lesson}
    return render(request, 'student/lesson_detail.html', context)

@login_required
@role_required(User.Role.STUDENT)
def assignment_submit(request, assignment_id):
    """View to submit an assignment."""
    assignment = get_object_or_404(Assignment, pk=assignment_id)
    if request.method == 'POST':
        form = SubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            submission = form.save(commit=False)
            submission.assignment = assignment
            submission.student = request.user
            submission.save()
            messages.success(request, "Assignment submitted successfully!")
            return redirect('course_detail', course_id=assignment.course.id)
    else:
        form = SubmissionForm()
    context = {
        'assignment': assignment,
        'form': form
    }
    return render(request, 'student/assignment_submit.html', context)

@login_required
@role_required(User.Role.STUDENT)
def quiz_attempt(request, quiz_id):
    """View to attempt a quiz."""
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    # Check if student is enrolled and has not already submitted the quiz
    if not Enrollment.objects.filter(student=request.user, course=quiz.course).exists() or \
       QuizSubmission.objects.filter(student=request.user, quiz=quiz).exists():
        messages.error(request, "You cannot attempt this quiz.")
        return redirect('course_detail', course_id=quiz.course.id)

    if request.method == 'POST':
        # Logic to grade the quiz submission
        score = 0
        total_questions = quiz.questions.count()
        submitted_choices_ids = request.POST.getlist('choices')
        
        correct_choices = Choice.objects.filter(is_correct=True, question__in=quiz.questions.all())
        correct_choices_ids = [str(c.id) for c in correct_choices]

        for choice_id in submitted_choices_ids:
            if choice_id in correct_choices_ids:
                score += 1
        
        final_score = (score / total_questions) * 100 if total_questions > 0 else 0
        
        submission = QuizSubmission.objects.create(
            quiz=quiz,
            student=request.user,
            score=final_score
        )
        submission.choices.set(submitted_choices_ids)
        messages.success(request, f"Quiz submitted! Your score is {final_score:.2f}%")
        return redirect('course_detail', course_id=quiz.course.id)

    context = {
        'quiz': quiz
    }
    return render(request, 'student/quiz_attempt.html', context)

@login_required
@role_required(User.Role.STUDENT)
def my_certificates(request):
    """View for a student to see their earned certificates."""
    certificates = Certificate.objects.filter(student=request.user)
    context = {'certificates': certificates}
    return render(request, 'student/my_certificates.html', context)

@login_required
@role_required(User.Role.STUDENT)
def support_ticket_create(request):
    """View for a student to create a new support ticket."""
    if request.method == 'POST':
        form = SupportTicketForm(request.POST)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.submitted_by = request.user
            ticket.save()
            messages.success(request, "Support ticket created successfully. We will get back to you shortly.")
            return redirect('student_dashboard')
    else:
        form = SupportTicketForm()
    context = {'form': form}
    return render(request, 'student/support_ticket_create.html', context)


# --- Instructor Views ---
@login_required
@role_required(role='INSTRUCTOR')
def instructor_dashboard(request):
    """
    Displays the instructor's main dashboard with a summary of their courses,
    students, and recent activities, including quizzes and assignments.
    """
    # Get all courses created by the current instructor
    instructor_courses = Course.objects.filter(instructor=request.user)

    # Annotate courses with student counts to display on the dashboard
    courses_with_stats = instructor_courses.annotate(
        student_count=Count('enrollment_set')
    )

    # Get a list of the 5 most recent students to enroll in any of the instructor's courses
    recent_students = User.objects.filter(
        enrollments__course__in=instructor_courses
    ).order_by('-enrollments__enrollment_date')[:5]

    # Get the 5 most recent quizzes created by the instructor
    recent_quizzes = Quiz.objects.filter(
        course__in=instructor_courses
    ).order_by('-created_at')[:5]

    # Get the 5 most recent assignments created by the instructor
    recent_assignments = Assignment.objects.filter(
        course__in=instructor_courses
    ).order_by('-created_at')[:5]

    # Count of students across all of the instructor's courses
    total_students = User.objects.filter(
        enrollments__course__in=instructor_courses
    ).distinct().count()

    total_quizzes = Quiz.objects.filter(course__in=instructor_courses).count()
    total_assignments = Assignment.objects.filter(course__in=instructor_courses).count()

    context = {
        'courses_with_stats': courses_with_stats,
        'recent_students': recent_students,
        'recent_quizzes': recent_quizzes,
        'recent_assignments': recent_assignments,
        'total_students': total_students,
        'total_quizzes': total_quizzes,
        'total_assignments': total_assignments,
    }
    return render(request, 'instructor/dashboard.html', context)

@login_required
@role_required(User.Role.INSTRUCTOR)
def instructor_courses(request):
    """View for an instructor to see their list of courses."""
    courses = Course.objects.filter(instructor=request.user)
    context = {'courses': courses}
    return render(request, 'instructor/courses.html', context)


@login_required
@role_required(User.Role.INSTRUCTOR)
def course_create(request):
    """View to create a new course."""
    if request.method == 'POST':
        form = CourseForm(request.POST)
        if form.is_valid():
            course = form.save(commit=False)
            course.instructor = request.user
            course.save()
            messages.success(request, f"Course '{course.title}' created successfully!")
            return redirect('instructor_courses')
    else:
        form = CourseForm()
    return render(request, 'instructor/course_create.html', {'form': form})

@login_required
@role_required(User.Role.INSTRUCTOR)
def course_edit(request, course_id):
    """View to edit an existing course."""
    course = get_object_or_404(Course, pk=course_id, instructor=request.user)
    if request.method == 'POST':
        form = CourseForm(request.POST, instance=course)
        if form.is_valid():
            form.save()
            messages.success(request, f"Course '{course.title}' updated successfully!")
            return redirect('instructor_courses')
    else:
        form = CourseForm(instance=course)
    return render(request, 'instructor/course_edit.html', {'form': form, 'course': course})

@login_required
@role_required(User.Role.INSTRUCTOR)
def lesson_create(request, course_id):
    """View to add a new lesson to a course."""
    course = get_object_or_404(Course, pk=course_id, instructor=request.user)
    if request.method == 'POST':
        form = LessonForm(request.POST, request.FILES)
        if form.is_valid():
            lesson = form.save(commit=False)
            lesson.course = course
            lesson.save()
            messages.success(request, "Lesson added successfully!")
            return redirect('course_edit', course_id=course.id)
    else:
        form = LessonForm()
    return render(request, 'instructor/lesson_create.html', {'form': form, 'course': course})

@login_required
@role_required(User.Role.INSTRUCTOR)
def assignment_create(request, course_id):
    """View to add a new assignment to a course."""
    course = get_object_or_404(Course, pk=course_id, instructor=request.user)
    if request.method == 'POST':
        form = AssignmentForm(request.POST)
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.course = course
            assignment.save()
            messages.success(request, "Assignment added successfully!")
            return redirect('course_edit', course_id=course.id)
    else:
        form = AssignmentForm()
    return render(request, 'instructor/assignment_create.html', {'form': form, 'course': course})

@login_required
@role_required(User.Role.INSTRUCTOR)
def quiz_create(request, course_id):
    """View to create a new quiz for a course."""
    course = get_object_or_404(Course, pk=course_id, instructor=request.user)
    if request.method == 'POST':
        form = QuizForm(request.POST)
        if form.is_valid():
            quiz = form.save(commit=False)
            quiz.course = course
            quiz.save()
            messages.success(request, "Quiz created successfully!")
            return redirect('course_edit', course_id=course.id)
    else:
        form = QuizForm()
    return render(request, 'instructor/quiz_create.html', {'form': form, 'course': course})

@login_required
@role_required(User.Role.INSTRUCTOR)
def submission_grade(request, submission_id):
    """View to grade a student submission."""
    submission = get_object_or_404(Submission, pk=submission_id, assignment__course__instructor=request.user)
    if request.method == 'POST':
        grade = request.POST.get('grade')
        feedback = request.POST.get('feedback')
        if grade:
            submission.grade = grade
        submission.feedback = feedback
        submission.save()
        messages.success(request, "Submission graded successfully.")
        return redirect('instructor_dashboard')
    
    context = {'submission': submission}
    return render(request, 'instructor/submission_grade.html', context)



@login_required
@role_required(User.Role.INSTRUCTOR)
def instructor_analytics(request):
    """
    Renders the analytics dashboard for instructors.
    It fetches and calculates key metrics related to the instructor's own courses.
    """
    # Get all courses taught by the current instructor
    instructor_courses = Course.objects.filter(instructor=request.user)
    
    # 1. Fetch Key Metrics
    total_courses = instructor_courses.count()
    
    # Count unique students enrolled in the instructor's courses
    total_students = User.objects.filter(
        enrollments__course__in=instructor_courses
    ).distinct().count()

    # Count open support tickets related to the instructor's courses
    open_tickets = SupportTicket.objects.filter(
        course__in=instructor_courses,
        status=SupportTicket.Status.OPEN
    ).count()

    # 2. Calculate Average Lesson Completion for the instructor's courses
    instructor_lessons = Lesson.objects.filter(course__in=instructor_courses)
    total_lessons = instructor_lessons.count()

    completed_lessons = StudentProgress.objects.filter(
        lesson__in=instructor_lessons, 
        is_completed=True
    ).count()

    if total_lessons > 0:
        avg_completion = (completed_lessons / total_lessons) * 100
    else:
        avg_completion = 0

    top_courses = instructor_courses.annotate(
        enrollment_count=Count('enrollment_set')
    ).order_by('-enrollment_count')[:5]

    context = {
        'total_students': total_students,
        'total_courses': total_courses,
        'open_tickets': open_tickets,
        'avg_completion': round(avg_completion, 2),
        'top_courses': top_courses,
    }
    
    return render(request, 'instructor/analytics.html', context)


# --- Admin Views ---
@login_required
@role_required(User.Role.ADMIN)
def moderator_dashboard(request):
    """Admin dashboard view."""
    total_users = User.objects.count()
    total_courses = Course.objects.count()
    total_tickets = SupportTicket.objects.filter(status=SupportTicket.Status.OPEN).count()
    
    context = {
        'total_users': total_users,
        'total_courses': total_courses,
        'total_tickets': total_tickets,
    }
    return render(request, 'moderator/dashboard.html', context)

@login_required
@role_required(User.Role.ADMIN)
def user_management(request):
    """View to manage users (students and instructors)."""
    users = User.objects.all().order_by('role')
    context = {'users': users}
    return render(request, 'moderator/user_management.html', context)

@login_required
@role_required(User.Role.ADMIN)
def create_instructor(request):
    """View to create a new instructor account."""
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.role = User.Role.INSTRUCTOR
            user.save()
            messages.success(request, f"Instructor '{user.username}' created successfully!")
            return redirect('user_management')
        else:
            for error in form.errors.values():
                messages.error(request, error)
    else:
        form = CustomUserCreationForm()
    return render(request, 'moderator/create_instructor.html', {'form': form})

@login_required
@role_required(User.Role.ADMIN)
def subscription_management(request):
    """View to manage and view subscriptions."""
    subscriptions = Subscription.objects.all().order_by('-start_date')
    context = {'subscriptions': subscriptions}
    return render(request, 'moderator/subscription_management.html', context)

@login_required
@role_required(User.Role.ADMIN)
def ticket_management(request):
    """View to manage support tickets."""
    tickets = SupportTicket.objects.all().order_by('status', '-created_at')
    context = {'tickets': tickets}
    return render(request, 'moderator/ticket_management.html', context)


@login_required
@role_required(role='STUDENT')
def mark_lesson_complete(request, lesson_id):
    """
    Handles marking a lesson as complete for a student.
    """
    if request.method == 'POST':
        user = request.user
        lesson = get_object_or_404(Lesson, id=lesson_id)
        
        try:
            # Use a transaction for database integrity
            with transaction.atomic():
                # Find or create the student's progress for this lesson
                progress, created = StudentProgress.objects.get_or_create(
                    student=user,
                    lesson=lesson,
                    defaults={'is_completed': True}
                )
                
                # If the progress entry already existed and was not completed, update it
                if not created and not progress.is_completed:
                    progress.is_completed = True
                    progress.save()
                    
                # Recalculate the student's course progress
                course = lesson.course
                total_lessons = course.lessons.count()
                if total_lessons > 0:
                    completed_lessons = StudentProgress.objects.filter(
                        student=user,
                        lesson__course=course,
                        is_completed=True
                    ).count()
                    
                    # Find the enrollment and update its progress
                    enrollment = Enrollment.objects.get(student=user, course=course)
                    enrollment.progress = (completed_lessons / total_lessons) * 100
                    enrollment.save()
                
                messages.success(request, f'Lesson "{lesson.title}" marked as complete!')
        
        except Enrollment.DoesNotExist:
            messages.error(request, 'You are not enrolled in this course.')
        except Exception as e:
            messages.error(request, f'An error occurred: {e}')

    return redirect('lesson_detail', lesson_id=lesson_id)


@login_required
@role_required(role='ADMIN')
def user_create(request):
    """
    Handles creating a new user account.
    """
    if request.method == 'POST':
        form = UserForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'User created successfully.')
            return redirect('user_management')
    else:
       form = AdminUserCreationForm()
    
    return render(request, 'moderator/user_form.html', {'form': form})


@login_required
@role_required(role='ADMIN')
def user_edit(request, user_id):
    """
    Handles editing an existing user's details.
    """
    user_obj = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        form = UserForm(request.POST, instance=user_obj)
        if form.is_valid():
            form.save()
            messages.success(request, f'User "{user_obj.username}" updated successfully.')
            return redirect('user_management')
    else:
        form = UserForm(instance=user_obj)
    
    return render(request, 'moderator/user_form.html', {'form': form, 'user_obj': user_obj})


@login_required
@role_required(role='ADMIN')
def user_delete(request, user_id):
    """
    Handles deleting a user account.
    """
    user_obj = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        user_obj.delete()
        messages.success(request, f'User "{user_obj.username}" deleted successfully.')
        return redirect('user_management')
    messages.error(request, 'Invalid request for user deletion.')
    return redirect('user_management')


@login_required
@role_required(role='ADMIN')
def ticket_detail(request, ticket_id):
    """
    Displays the details of a single support ticket.
    """
    ticket = get_object_or_404(SupportTicket, id=ticket_id)
    return render(request, 'moderator/ticket_detail.html', {'ticket': ticket})


@login_required
@role_required(role='ADMIN')
def ticket_resolve(request, ticket_id):
    """
    Handles resolving a support ticket.
    """
    ticket = get_object_or_404(SupportTicket, id=ticket_id)
    if request.method == 'POST':
        if ticket.status == SupportTicket.Status.OPEN:
            ticket.status = SupportTicket.Status.RESOLVED
            ticket.save()
            messages.success(request, f'Ticket "{ticket.subject}" has been resolved.')
    return redirect('ticket_management')
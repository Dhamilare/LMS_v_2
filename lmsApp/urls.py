from django.urls import path
from . import views

urlpatterns = [
    # --- Authentication URLs ---
    path('accounts/register/', views.register_view, name='register'),
    path('accounts/login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('', views.dashboard_view, name='dashboard'),

    # --- Student URLs ---
    path('student/dashboard/', views.student_dashboard, name='student_dashboard'),
    path('student/my-courses/', views.my_courses, name='my_courses'),
    path('student/course/<int:course_id>/', views.course_detail, name='course_detail'),
    path('student/lesson/<int:lesson_id>/', views.lesson_detail, name='lesson_detail'),
    path('student/assignment/<int:assignment_id>/submit/', views.assignment_submit, name='assignment_submit'),
    path('student/quiz/<int:quiz_id>/attempt/', views.quiz_attempt, name='quiz_attempt'),
    path('student/my-certificates/', views.my_certificates, name='my_certificates'),
    path('student/support/create/', views.support_ticket_create, name='support_ticket_create'),
    
    path('lessons/<int:lesson_id>/mark_complete/', views.mark_lesson_complete, name='mark_lesson_complete'),

    # --- Instructor URLs ---
    path('instructor/dashboard/', views.instructor_dashboard, name='instructor_dashboard'),
    path('instructor/courses/', views.instructor_courses, name='instructor_courses'),
    path('instructor/courses/create/', views.course_create, name='course_create'),
    path('instructor/courses/<int:course_id>/edit/', views.course_edit, name='course_edit'),
    path('instructor/courses/<int:course_id>/lessons/create/', views.lesson_create, name='lesson_create'),
    path('instructor/courses/<int:course_id>/assignments/create/', views.assignment_create, name='assignment_create'),
    path('instructor/courses/<int:course_id>/quizzes/create/', views.quiz_create, name='quiz_create'),
    path('instructor/submissions/grade/<int:submission_id>/', views.submission_grade, name='submission_grade'),
    path('instructor/analytics/', views.instructor_analytics, name='instructor_analytics'),

    # --- Moderator URLs ---
    path('moderator/dashboard/', views.moderator_dashboard, name='moderator_dashboard'),
    path('moderator/users/', views.user_management, name='user_management'),
    path('moderator/users/create/', views.user_create, name='user_create'),
    path('moderator/users/<int:user_id>/edit/', views.user_edit, name='user_edit'),
    path('moderator/users/<int:user_id>/delete/', views.user_delete, name='user_delete'),
    path('moderator/subscriptions/', views.subscription_management, name='subscription_management'),
    path('moderator/tickets/', views.ticket_management, name='ticket_management'),
    path('moderator/tickets/<int:ticket_id>/detail/', views.ticket_detail, name='ticket_detail'),
    path('moderator/tickets/<int:ticket_id>/resolve/', views.ticket_resolve, name='ticket_resolve'),
]
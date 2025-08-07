from django.urls import path
from . import views

urlpatterns = [
    # --- Authentication & General Views ---
    path('accounts/register/', views.student_register, name='register'),
    path('accounts/login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('', views.dashboard, name='dashboard'),

    # --- Admin Functionality ---
    path('create-instructor/', views.create_instructor, name='create_instructor'),
    path('instructors/', views.instructor_list, name='instructor_list'), 
    path('instructors/<int:pk>/edit/', views.instructor_update, name='instructor_update'),
    path('instructors/<int:pk>/delete/', views.instructor_delete, name='instructor_delete'), 
    path('audit-logs/', views.audit_logs, name='audit_logs'),

    # --- Instructor Course Management ---
    path('courses/', views.course_list, name='course_list'), # Instructor's list of courses
    path('courses/create/', views.course_create, name='course_create'),
    path('courses/<slug:slug>/edit/', views.course_update, name='course_update'),
    path('courses/<slug:slug>/delete/', views.course_delete, name='course_delete'), 

    # --- Student Course Enrollment & Detail ---
    path('student_courses/', views.all_courses, name='all_courses'), 
    path('courses/<slug:slug>/', views.course_detail, name='course_detail'),
    path('courses/<slug:slug>/enroll/', views.enroll_course, name='enroll_course'),
    path('courses/<slug:course_slug>/transcript/', views.course_transcript, name='course_transcript'),

    # --- Progress Tracking (Content Completion) ---
    path('courses/<slug:course_slug>/modules/<int:module_id>/lessons/<int:lesson_id>/contents/<int:content_id>/mark-completed/', views.mark_content_completed, name='mark_content_completed'),

    # --- Certificate Functionality ---
    path('courses/<slug:course_slug>/issue-certificate/', views.issue_certificate, name='issue_certificate'),
    path('certificates/<uuid:certificate_id>/view/', views.view_certificate, name='view_certificate'),
    path('certificates/', views.certificate_catalog, name='certificate_catalog'),

    # --- Module Management (Instructor) ---
    path('courses/<slug:course_slug>/modules/create/', views.module_create, name='module_create'),
    path('courses/<slug:course_slug>/modules/<int:module_id>/edit/', views.module_update, name='module_update'),
    path('courses/<slug:course_slug>/modules/<int:module_id>/delete/', views.module_delete, name='module_delete'),

    # --- Lesson Management (Instructor) ---
    path('courses/<slug:course_slug>/modules/<int:module_id>/lessons/create/', views.lesson_create, name='lesson_create'),
    path('courses/<slug:course_slug>/modules/<int:module_id>/lessons/<int:lesson_id>/edit/', views.lesson_update, name='lesson_update'),
    path('courses/<slug:course_slug>/modules/<int:module_id>/lessons/<int:lesson_id>/delete/', views.lesson_delete, name='lesson_delete'),

    # --- Content Management (Instructor) ---
    path('courses/<slug:course_slug>/modules/<int:module_id>/lessons/<int:lesson_id>/contents/create/', views.content_create, name='content_create'),
    path('courses/<slug:course_slug>/modules/<int:module_id>/lessons/<int:lesson_id>/contents/<int:content_id>/edit/', views.content_update, name='content_update'),
    path('courses/<slug:course_slug>/modules/<int:module_id>/lessons/<int:lesson_id>/contents/<int:content_id>/delete/', views.content_delete, name='content_delete'),
    path('courses/<slug:course_slug>/modules/<int:module_id>/lessons/<int:lesson_id>/contents/<int:content_id>/', views.content_detail, name='content_detail'), 
   
    # --- Instructor Quiz Management ---
    path('instructor/quizzes/', views.quiz_list_instructor, name='quiz_list_instructor'), 
    path('instructor/quizzes/create/', views.quiz_create, name='quiz_create'), 
    path('instructor/quizzes/<int:quiz_id>/manage/', views.quiz_detail_manage, name='quiz_detail_manage'), 
    path('instructor/quizzes/<int:quiz_id>/questions/create/', views.question_create, name='question_create'), 
    path('instructor/quizzes/<int:quiz_id>/questions/<int:question_id>/update/', views.question_update, name='question_update'), 
    path('instructor/quizzes/<int:quiz_id>/questions/<int:question_id>/delete/', views.question_delete, name='question_delete'), 
    path('instructor/quizzes/<int:quiz_id>/assign_to_course/', views.quiz_assign_to_course, name='quiz_assign_to_course'), 
    path('instructor/quizzes/<int:quiz_id>/upload_csv/', views.quiz_upload_csv, name='quiz_upload_csv'), 
    path('instructor/quizzes/download_csv_template/', views.quiz_download_csv_template, name='quiz_download_csv_template'), 

    # --- Student Course-Level Quiz Interaction
    path('courses/<slug:course_slug>/take_quiz/', views.quiz_take, name='quiz_take'), 
    path('courses/<slug:course_slug>/submit_quiz/', views.quiz_submit, name='quiz_submit'), 
    path('courses/<slug:course_slug>/quiz_result/<int:attempt_id>/', views.quiz_result, name='quiz_result'),
]

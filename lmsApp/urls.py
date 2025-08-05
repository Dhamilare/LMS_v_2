from django.urls import path
from . import views

urlpatterns = [
    path('accounts/register/', views.student_register, name='register'),
    path('accounts/login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('', views.dashboard, name='dashboard'),

    # Admin Functionality
    path('create-instructor/', views.create_instructor, name='create_instructor'),
    path('instructors/', views.instructor_list, name='instructor_list'), 
    path('instructors/<int:pk>/edit/', views.instructor_update, name='instructor_update'),
    path('instructors/<int:pk>/delete/', views.instructor_delete, name='instructor_delete'), 

    # Instructor Course Management
    path('courses/', views.course_list, name='course_list'),
    path('courses/create/', views.course_create, name='course_create'),
    path('courses/<slug:slug>/edit/', views.course_update, name='course_update'),
    path('courses/<slug:slug>/delete/', views.course_delete, name='course_delete'), 

    # Course Detail and Content Management
    path('student_courses/', views.all_courses, name='all_courses'),
    path('courses/<slug:slug>/', views.course_detail, name='course_detail'),
    path('courses/<slug:slug>/enroll/', views.enroll_course, name='enroll_course'),

    # Progress Tracking
    path('courses/<slug:course_slug>/modules/<int:module_id>/lessons/<int:lesson_id>/contents/<int:content_id>/mark-completed/', views.mark_content_completed, name='mark_content_completed'),

    # Certificate Functionality (NEW)
    path('courses/<slug:course_slug>/issue-certificate/', views.issue_certificate, name='issue_certificate'),
    path('certificates/<uuid:certificate_id>/view/', views.view_certificate, name='view_certificate'),
    path('certificates/', views.certificate_catalog, name='certificate_catalog'),

    # Module Management (Nested under course)
    path('courses/<slug:course_slug>/modules/create/', views.module_create, name='module_create'),
    path('courses/<slug:course_slug>/modules/<int:module_id>/edit/', views.module_update, name='module_update'),
    path('courses/<slug:course_slug>/modules/<int:module_id>/delete/', views.module_delete, name='module_delete'),

    # Lesson Management (Nested under module)
    path('courses/<slug:course_slug>/modules/<int:module_id>/lessons/create/', views.lesson_create, name='lesson_create'),
    path('courses/<slug:course_slug>/modules/<int:module_id>/lessons/<int:lesson_id>/edit/', views.lesson_update, name='lesson_update'),
    path('courses/<slug:course_slug>/modules/<int:module_id>/lessons/<int:lesson_id>/delete/', views.lesson_delete, name='lesson_delete'),

    # Content Management (Nested under lesson)
    path('courses/<slug:course_slug>/modules/<int:module_id>/lessons/<int:lesson_id>/contents/create/', views.content_create, name='content_create'),
    path('courses/<slug:course_slug>/modules/<int:module_id>/lessons/<int:lesson_id>/contents/<int:content_id>/edit/', views.content_update, name='content_update'),
    path('courses/<slug:course_slug>/modules/<int:module_id>/lessons/<int:lesson_id>/contents/<int:content_id>/delete/', views.content_delete, name='content_delete'),
    path('courses/<slug:course_slug>/modules/<int:module_id>/lessons/<int:lesson_id>/contents/<int:content_id>/', views.content_detail, name='content_detail'),
]



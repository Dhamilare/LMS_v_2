from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings
from datetime import datetime
from django.contrib.sites.shortcuts import get_current_site
import traceback
from django.contrib.sites.shortcuts import get_current_site
from django.http import HttpRequest
from django.urls import reverse
from urllib.parse import urljoin


def send_templated_email(template_name, subject, recipient_list, context, attachments=None):

    context['current_year'] = datetime.now().year
    if 'protocol' not in context or 'domain' not in context:
        try:
            request = context.get('request', HttpRequest())
            current_site = get_current_site(request)
            context['protocol'] = 'https' if request.is_secure() else 'http'
            context['domain'] = current_site.domain
        except Exception:
            context['protocol'] = 'http'
            context['domain'] = 'localhost'

    html_content = render_to_string(template_name, context)
    email = EmailMessage(
        subject,
        html_content,
        settings.EMAIL_SENDER,
        recipient_list
    )
    email.content_subtype = "html" 

    if attachments:
        for filename, content, mimetype in attachments:
            email.attach(filename, content, mimetype)
    
    try:
        email.send()
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        traceback.print_exc()
        return False
    

def build_absolute_url(request=None, url_path=""):

    if request:
        try:
            return request.build_absolute_uri(url_path)
        except Exception:
            pass

    domain = getattr(settings, 'ABSOLUTE_URL_DOMAIN', 'localhost')
    
    if not settings.DEBUG:
        default_protocol = 'https'
    else:
        default_protocol = 'http'
        
    protocol = getattr(settings, 'ABSOLUTE_URL_PROTOCOL', default_protocol)

    base_url = f"{protocol}://{domain}"
    return urljoin(base_url, url_path)



def send_course_notification(course, matching_students, action_type, request=None):
    """
    Sends a personalized email notification to matching students using send_templated_email.
    """
    recipient_list = list(matching_students.values_list('email', flat=True).distinct())
    if not recipient_list:
        return

    url_path = reverse('course_detail', args=[course.slug])
    course_url = build_absolute_url(request, url_path)

    subject = f"New Course Alert: {course.title} is now {action_type}!"

    for student in matching_students:
        subject = f"New Course Alert: {course.title} is now {action_type}!"
        student_name = student.get_full_name() or student.first_name or student.email.split('@')[0]
        
        try:
            if hasattr(course, 'instructor') and callable(getattr(course.instructor, 'get_full_name', None)):
                instructor_name = course.instructor.get_full_name()
            else:
                instructor_name = 'The LMS Team'
        except Exception:
            instructor_name = 'The LMS Team'

    context = {
        'course_title': course.title,
        'student_name': student_name,
        'instructor_name': instructor_name,
        'action_type': action_type,
        'course_description': course.description,
        'course_url': course_url,
    }

    send_templated_email(
        template_name='emails/new_course_notification.html',
        subject=subject,
        recipient_list=[student.email],
        context=context
    )

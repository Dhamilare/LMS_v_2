from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings
from datetime import datetime
from django.contrib.sites.shortcuts import get_current_site
import traceback
from django.contrib.sites.shortcuts import get_current_site
from django.http import HttpRequest
from django.urls import reverse

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
    


def build_absolute_url(request, url_path):
    """
    Safely builds a full absolute URL whether request is available or not.
    """

    # If request was passed → use it (most accurate)
    if request:
        try:
            return request.build_absolute_uri(url_path)
        except:
            pass

    # If no request → fallback to Sites framework
    try:
        fake_request = HttpRequest()
        domain = get_current_site(fake_request).domain
    except:
        domain = "localhost"

    protocol = "https"
    return f"{protocol}://{domain}{url_path}"

def send_course_notification(course, matching_students, action_type, request=None):
    """
    Sends a personalized email notification to matching students using send_templated_email.
    """
    recipient_list = list(matching_students.values_list('email', flat=True).distinct())
    if not recipient_list:
        return

    subject = f"New Course Alert: {course.title} is now {action_type}!"
    context = {
        'course_title': course.title,
        'action_type': action_type,
        'course_description': course.description,
        'course_url': request.build_absolute_url(reverse('course_detail', args=[course.slug])) if request else settings.BASE_URL + reverse('course_detail', args=[course.slug])
    }

    send_templated_email(
        template_name='emails/new_course_notification.html',
        subject=subject,
        recipient_list=recipient_list,
        context=context
    )

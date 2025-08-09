# core/utils.py
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings
from datetime import datetime
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.sites.shortcuts import get_current_site

def send_templated_email(template_name, subject, recipient_list, context, attachments=None):

    context['current_year'] = datetime.now().year

    html_content = render_to_string(template_name, context)
    
    email = EmailMessage(
        subject,
        html_content,
        settings.DEFAULT_FROM_EMAIL,
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
        # Log the error for debugging
        import traceback
        print(f"Error sending email: {e}\n{traceback.format_exc()}")
        return False


def send_custom_password_reset_email(user, request):
    """
    Sends a styled multi-part password reset email using send_templated_email().
    """
    current_site = get_current_site(request)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)

    context = {
        "protocol": "https" if request.is_secure() else "http",
        "domain": current_site.domain,
        # "site_name": current_site.name, # Added for branding
        "uid": uid,
        "token": token,
        "user": user
    }

    send_templated_email(
        template_name="accounts/password_reset_email.html",
        subject="LMS Password Reset Request",
        recipient_list=[user.email],
        context=context
    )
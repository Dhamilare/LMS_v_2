from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings
from datetime import datetime
from django.contrib.sites.shortcuts import get_current_site
import traceback
from django.contrib.sites.shortcuts import get_current_site
from django.http import HttpRequest

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
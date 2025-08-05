# core/utils.py
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings
from datetime import datetime

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


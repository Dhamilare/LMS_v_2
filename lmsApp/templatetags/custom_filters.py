from django import template
from django.utils.safestring import mark_safe
from urllib.parse import quote_plus
import json
from urllib.parse import urlparse, parse_qs

register = template.Library()

@register.filter
def js(value):
    """Safely escapes a value for use as a JavaScript string literal."""
    return mark_safe(json.dumps(value))

register = template.Library()

@register.filter
def youtube_embed_url(url):
    if not url:
        return ""

    parsed = urlparse(url)
    video_id = None

    # Handle standard youtube.com URLs (like the one in your database)
    if parsed.hostname in ["www.youtube.com", "youtube.com"]:
        if "/shorts/" in parsed.path:
            video_id = parsed.path.split("/")[-1]
        else:
            # parse_qs returns {'v': ['h95cQkEWBx0']}. We need the [0] element.
            video_ids = parse_qs(parsed.query).get("v")
            if video_ids:
                video_id = video_ids[0]

    # Handle youtu.be short URLs
    elif parsed.hostname == "youtu.be":
        video_id = parsed.path.lstrip("/")

    if video_id:
        # Return the clean URL: https://www.youtube.com/embed/h95cQkEWBx0
        return mark_safe(f"https://www.youtube.com/embed/{video_id}")

    return ""


@register.filter
def split(value, arg):
    """
    Splits a string by the given argument.
    """
    if isinstance(value, str):
        return value.split(arg)
    return value

@register.filter
def replace(value, arg):
    """
    Replaces all occurrences of a substring with another substring.
    """
    if not isinstance(value, str) or not isinstance(arg, str):
        return value
        
    try:
        old, new = arg.split(',', 1) 
        return mark_safe(value.replace(old, new))
    except ValueError:
        return value


@register.filter(name='embed_document')
def embed_document(url):
    """
    Generates an embeddable URL for documents using the Microsoft Office Online Viewer 
    (for PPTX, DOCX, XLSX) or the browser's native viewer (for PDF).
    This solution is robust and requires the file URL to be public (e.g., Azure Blob/SharePoint).
    """
    if not url:
        return ""
    
    file_type = url.split('.')[-1].lower()
    encoded_url = quote_plus(url) 

    if file_type in ['ppt', 'pptx', 'doc', 'docx', 'xls', 'xlsx']:
        embed_url = f"https://view.officeapps.live.com/op/embed.aspx?src={encoded_url}"
        return mark_safe(embed_url)

    elif file_type == 'pdf':
        return mark_safe(url)
    return mark_safe(url)
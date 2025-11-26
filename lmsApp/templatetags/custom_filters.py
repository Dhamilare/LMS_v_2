from django import template
from django.utils.safestring import mark_safe
from urllib.parse import quote_plus
import json
import re

register = template.Library()

@register.filter
def js(value):
    """Safely escapes a value for use as a JavaScript string literal."""
    return mark_safe(json.dumps(value))

@register.filter
def youtube_embed_url(url):
    """
    Converts a standard YouTube watch URL to an embed URL.
    """
    if url and "youtube.com/watch?v=" in url:
        return url.replace("watch?v=", "embed/")
    return url

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
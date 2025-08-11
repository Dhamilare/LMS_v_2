from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter
def replace(value, arg):
    if isinstance(value, str) and isinstance(arg, str):
        try:
            old, new = arg.split(',')
            return value.replace(old, new)
        except ValueError:
            return value
    return value


@register.filter
def youtube_embed_url(url):
    """
    Converts a standard YouTube watch URL to an embed URL.
    Example: https://www.youtube.com/watch?v=dQw4w9WgXcQ
    Becomes: https://www.youtube.com/embed/dQw4w9WgXcQ
    """
    if url and "youtube.com/watch?v=" in url:
        return url.replace("watch?v=", "embed/")
    return url

@register.filter
def split(value, arg):
    """
    Splits a string by the given argument.
    Usage: {{ value|split:',' }}
    """
    return value.split(arg)

@register.filter
def replace(value, arg):
    """
    Replaces all occurrences of a substring with another substring.
    Usage: {{ value|replace:"old,new" }}
    Note: This custom filter is provided to replace the problematic one.
          The arguments for this custom 'replace' should be passed as a single string
          separated by a comma, e.g., "old_string,new_string".
    """
    try:
        old, new = arg.split(',', 1) # Split only on the first comma
        return value.replace(old, new)
    except ValueError:
        return value # Return original value if splitting fails (e.g., no comma)


@register.filter(name='embed_document')
def embed_document(url):
    """
    Generates a URL for embedding PDFs and PPTs using Google Docs Viewer.
    Assumes the URL is a direct link to the file.
    
    Usage:
    <iframe src="{{ file.url|embed_document }}" style="..."></iframe>
    """
    if not url:
        return ""
    
    # Check the file extension to see if it's a type that Google Docs Viewer can handle
    # and if it's not already a youtube video.
    file_type = url.split('.')[-1].lower()
    
    if file_type in ['pdf', 'ppt', 'pptx', 'doc', 'docx', 'xls', 'xlsx']:
        # Google Docs Viewer URL format
        embed_url = f"https://docs.google.com/gview?url={url}&embedded=true"
        return mark_safe(embed_url)
    
    # If it's not a known document type, return the original URL
    return mark_safe(url)

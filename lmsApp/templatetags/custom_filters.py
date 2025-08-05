from django import template

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



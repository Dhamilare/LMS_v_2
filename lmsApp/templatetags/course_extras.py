from django import template

register = template.Library()

@register.filter
def format_duration(total_minutes):
    """
    Converts a duration in minutes into a human-readable format like '1h 5m'.
    """
    if total_minutes is None:
        return ""
    
    hours = total_minutes // 60
    minutes = total_minutes % 60
    
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    
    return " ".join(parts) if parts else "0m"
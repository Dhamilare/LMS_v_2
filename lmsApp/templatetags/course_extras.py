from django import template
from django.utils.html import format_html

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


@register.filter
def star_rating(value):
    """
    Converts a decimal rating into HTML star icons.
    e.g., 4.5 -> ★★★★☆
    """
    # Round to the nearest 0.5 for half-star display
    rating = round(value * 2) / 2
    
    full_stars = int(rating)
    half_star = 1 if rating % 1 == 0.5 else 0
    empty_stars = 5 - full_stars - half_star
    
    # Use Font Awesome icons for display
    html_output = ''
    # Full stars
    for _ in range(full_stars):
        html_output += '<i class="fas fa-star text-yellow-400"></i>'
    # Half star
    if half_star:
        html_output += '<i class="fas fa-star-half-alt text-yellow-400"></i>'
    # Empty stars
    for _ in range(empty_stars):
        html_output += '<i class="far fa-star text-gray-300"></i>'

    return format_html(html_output)
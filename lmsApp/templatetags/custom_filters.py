import markdown
from django import template
from django.template.defaultfilters import stringfilter

# This registers the template library so Django can find our tags
register = template.Library()

@register.filter
@stringfilter
def markdown_to_html(value):
    return markdown.markdown(value, extensions=['fenced_code', 'tables'])


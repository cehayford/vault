"""Template filters for voting app. Use for safe output (e.g. hex colors in CSS)."""
import re
from django import template

register = template.Library()

HEX_COLOR_RE = re.compile(r'^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$')


@register.filter
def valid_hex_color(value):
    """Return value only if it is a valid hex color (#RGB or #RRGGBB); otherwise empty string. Use when outputting in CSS."""
    if not value or not isinstance(value, str):
        return ''
    value = value.strip()
    if HEX_COLOR_RE.match(value):
        if len(value) == 7:
            return value.lower()
        return '#' + value[1] * 2 + value[2] * 2 + value[3] * 2
    return ''

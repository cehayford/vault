from django import template
from django.conf import settings

register = template.Library()


@register.simple_tag
def google_oauth_enabled():
    """True if Google OAuth client_id is configured (avoids redirect with missing client_id)."""
    return getattr(settings, 'GOOGLE_OAUTH_ENABLED', False)

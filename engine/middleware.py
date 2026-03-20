"""
Middleware to avoid IntegrityError when django-axes logs login:
axes_accesslog.session_hash is NOT NULL, but request.session.session_key can be None
until session is saved (e.g. on /accounts/login/ via allauth).
Ensuring session has a key before view runs fixes axes logging.
"""


class EnsureSessionKeyMiddleware:
    """Force session to have a key before login views run (avoids axes_accesslog.session_hash NOT NULL)."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.rstrip('/') in ('/accounts/login', '/accounts/signup', '/login', '/signup') and not request.session.session_key:
            request.session.create()
        return self.get_response(request)

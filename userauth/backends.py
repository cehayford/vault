from django.contrib.auth.backends import BaseBackend
from .models import CustomUser


class EmailBackend(BaseBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        raw = (username or kwargs.get('email') or '').strip()
        if not raw or not password:
            return None
        email = CustomUser.objects.normalize_email(raw)
        try:
            user = CustomUser.objects.get(email__iexact=email)
            if user.check_password(password):
                return user
        except CustomUser.DoesNotExist:
            return None
        return None

    def get_user(self, user_id):
        try:
            return CustomUser.objects.get(pk=user_id)
        except CustomUser.DoesNotExist:
            return None
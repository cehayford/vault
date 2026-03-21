from django.urls import path
from .views import (
    home, signin, signup, email_verification, resend_verification, signout,
    mfa_setup, mfa_verify, mfa_disable, profile,
    phone_verify, send_phone_otp_view,
    about, help_center, contact, privacy_policy, terms_of_service, faq,
    password_reset, password_reset_done, password_reset_complete, reset_password_confirm,
)
from .celery_views import (
    celery_health_api, celery_simple_health, celery_metrics_detail, 
    celery_test_task, celery_clear_cache, CeleryHealthView
)

app_name = 'userauth'

urlpatterns = [
    path('', home, name='home'),
    path('login/', signin, name='login'),
    path('signup/', signup, name='signup'),
    path('verify-email/', email_verification, name='email_verification'),
    path('resend-verification/', resend_verification, name='resend_verification'),
    path('logout/', signout, name='logout'),
    path('mfa-setup/', mfa_setup, name='mfa_setup'),
    path('mfa-verify/', mfa_verify, name='mfa_verify'),
    path('mfa-disable/', mfa_disable, name='mfa_disable'),
    path('profile/', profile, name='profile'),
    path('phone-verify/', phone_verify, name='phone_verify'),
    path('phone-send-otp/', send_phone_otp_view, name='send_phone_otp'),
    path('about/', about, name='about'),
    path('help/', help_center, name='help'),
    path('contact/', contact, name='contact'),
    path('privacy/', privacy_policy, name='privacy'),
    path('terms/', terms_of_service, name='terms'),
    path('faq/', faq, name='faq'),
    path('password-reset/', password_reset, name='password_reset'),
    path('password-reset/done/', password_reset_done, name='password_reset_done'),
    path('password-reset/<uidb64>/<token>/', reset_password_confirm, name='password_reset_confirm'),
    path('password-reset/complete/', password_reset_complete, name='password_reset_complete'),
    
    # Celery monitoring URLs
    path('celery/health/', CeleryHealthView.as_view(), name='celery_health'),
    path('celery/api/health/', celery_health_api, name='celery_health_api'),
    path('celery/api/simple/', celery_simple_health, name='celery_simple_health'),
    path('celery/api/metrics/', celery_metrics_detail, name='celery_metrics_detail'),
    path('celery/api/test/', celery_test_task, name='celery_test_task'),
    path('celery/api/clear-cache/', celery_clear_cache, name='celery_clear_cache'),
]
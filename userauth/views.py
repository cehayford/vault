from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from django.template.loader import render_to_string
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.conf import settings
from django.utils import timezone
from django.contrib.sites.shortcuts import get_current_site
from django.urls import reverse
from django.utils.html import strip_tags
from django.utils.http import url_has_allowed_host_and_scheme
from .models import CustomUser, EmailVerification, MFASession, SecurityLog
from .forms import UserSignUp, LoginForm, UserSignUp
from voting.tasks import send_phone_otp
import pyotp
from django_ratelimit.decorators import ratelimit
import logging
import qrcode
from io import BytesIO
from base64 import b64encode
import json



def _get_safe_next_url(request, default=None):
    next_url = request.POST.get('next') or request.GET.get('next') or ''
    if not next_url or not next_url.strip():
        return default
    next_url = next_url.strip()
    allowed_hosts = {request.get_host(), *getattr(settings, 'ALLOWED_HOSTS', [])}
    if url_has_allowed_host_and_scheme(next_url, allowed_hosts=allowed_hosts, require_https=not settings.DEBUG):
        return next_url
    return default
try:
    from django_ratelimit.decorators import ratelimit
except ImportError:
    def ratelimit(*args, **kwargs):
        def noop(f):
            return f
        return noop


def home(request):
    if request.user.is_authenticated:
        return redirect('voting:dashboard')
    return render(request, 'userauth/home.html')


@ratelimit(key='ip', rate='10/m', method='POST', block=False)
@ratelimit(key='post:email', rate='5/m', method='POST', block=False)
@csrf_protect
def signin(request):
    if getattr(request, 'ratelimited', False):
        messages.error(request, 'Too many login attempts. Try again later.')
        return redirect('userauth:login')
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if user is not None:
                email_domain = (user.email or '').split('@')[-1].lower()
                if email_domain in BLOCKED_EMAIL_DOMAINS:
                    messages.error(
                        request,
                        'Accounts with this email domain are not permitted to sign in.',
                    )
                    return redirect('userauth:login')
                if getattr(user, 'account_locked', False):
                    SecurityLog.objects.create(
                        user=user,
                        action_type='login_failed',
                        description='Login attempt while account locked',
                        ip_address=request.META.get('REMOTE_ADDR'),
                        user_agent=request.META.get('HTTP_USER_AGENT'),
                        success=False
                    )
                    messages.error(request, 'This account is locked. Contact support to unlock.')
                    return redirect('userauth:login')
                if user.mfa_enabled:
                    # Create MFA session
                    mfa_session = MFASession.objects.create(
                        user=user,
                        session_token=default_token_generator.make_token(user),
                        expires_at=timezone.now() + timezone.timedelta(minutes=10)
                    )
                    next_url = _get_safe_next_url(request)
                    if next_url:
                        if not request.session.session_key:
                            request.session.create()
                        request.session['login_next'] = next_url
                    SecurityLog.objects.create(
                        user=user,
                        action_type='login',
                        description='Login successful, MFA required',
                        ip_address=request.META.get('REMOTE_ADDR'),
                        user_agent=request.META.get('HTTP_USER_AGENT'),
                        success=True
                    )
                    return redirect(
                        reverse('userauth:mfa_verify') + '?token=' + mfa_session.session_token
                    )
                else:
                    if not request.session.session_key:
                        request.session.create()
                    login(request, user, backend='userauth.backends.EmailBackend')
                    SecurityLog.objects.create(
                        user=user,
                        action_type='login',
                        description='Login successful',
                        ip_address=request.META.get('REMOTE_ADDR'),
                        user_agent=request.META.get('HTTP_USER_AGENT'),
                        success=True
                    )
                    messages.success(request, f'Welcome back, {user.first_name}!')
                    next_url = _get_safe_next_url(request)
                    if not next_url:
                        if user.role == 'super_admin':
                            next_url = reverse('voting:admin_dashboard')
                        elif user.role == 'election_admin':
                            next_url = reverse('voting:election_list')
                        else:
                            next_url = reverse('voting:dashboard')
                    return redirect(next_url)
    else:
        form = LoginForm(request)
    
    return render(request, 'userauth/login.html', {
        'form': form,
        'next': _get_safe_next_url(request) or '',
    })


# Disposable/temporary email domains blocked per Part 13 (Sybil controls)
BLOCKED_EMAIL_DOMAINS = [
    'mailinator.com', 'guerrillamail.com', 'tempmail.com',
    'throwaway.email', 'yopmail.com', 'sharklasers.com',
]


@ratelimit(key='ip', rate='5/h', method='POST', block=False)
@csrf_protect
def signup(request):
    if getattr(request, 'ratelimited', False):
        messages.error(request, 'Too many registration attempts. Try again later.')
        return redirect('userauth:signup')
    if request.method == 'POST':
        form = UserSignUp(request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('email')
            email_domain = email.split('@')[1].lower() if '@' in email else ''
            if email_domain in BLOCKED_EMAIL_DOMAINS:
                form.add_error(
                    'email',
                    'Disposable or temporary email addresses are not permitted.',
                )
                return render(request, 'userauth/signup.html', {'form': form, 'next': request.POST.get('next', '')})
            nickname = form.cleaned_data.get('nickname')
            password = form.cleaned_data.get('password')
            last_name = form.cleaned_data.get('last_name')
            first_name = form.cleaned_data.get('first_name')
            user = CustomUser.objects.create_user(
                email=email,
                nickname=nickname,
                password=password,
                last_name=last_name,
                first_name=first_name,
                is_active=False,
                is_verified=False
            )
            verify_user = EmailVerification.objects.create(user=user)
            token = verify_user.generate_code()
            verify_user.code = token
            verify_user.save()
            current_site = get_current_site(request)
            subject = 'Verify Your Email Address'
            message = render_to_string('userauth/email_verification.html', {
                'user': user,
                'token': token,
                'domain': current_site.domain,
            })
            
            # Try to send via Celery for better reliability
            try:
                from celery_app import send_email_notification
                result = send_email_notification.delay(
                    email,
                    subject,
                    message,
                    html_message=message
                )
                # Check if task was successful (for immediate feedback)
                if result and hasattr(result, 'result'):
                    task_result = result.result
                    if task_result and task_result.get('status') == 'failed':
                        # Log the failure but continue with signup
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f'Email task failed for {email}: {task_result.get("error")}')
            except Exception as e:
                # Fallback to direct email sending if Celery is not available
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f'Celery not available, falling back to direct email: {e}')
                try:
                    send_mail(
                        subject,
                        message,
                        getattr(settings, 'DEFAULT_FROM_EMAIL', settings.EMAIL_FROM_ADDRESS),
                        [email],
                        fail_silently=False,
                    )
                except Exception as email_error:
                    logger.warning(f'Direct email also failed for {email}: {email_error}')
                    # In production with console backend, email will be printed to logs
                    # so user can still get verification code from logs if needed
            domain = get_current_site(request).domain
            ctx = {'domain': domain}
            if settings.DEBUG:
                ctx['verification_code'] = token
            return render(request, 'userauth/checkemailmsg.html', ctx)
        return render(request, 'userauth/signup.html', {'form': form, 'next': _get_safe_next_url(request) or ''})
    prefilled_email = request.GET.get('email', '')
    form = UserSignUp(initial={'email': prefilled_email} if prefilled_email else None)
    return render(request, 'userauth/signup.html', {'form': form, 'next': _get_safe_next_url(request) or ''})


@require_http_methods(['POST'])
def signout(request):
    logout(request)
    return redirect('/')
     

@ratelimit(key='ip', rate='5/h', method='POST', block=False)
@csrf_protect
def password_reset(request):
    if getattr(request, 'ratelimited', False):
        return redirect('userauth:password_reset_done')
    if request.method == 'POST':
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('email')
            try:
                user = CustomUser.objects.get(email__iexact=email)
                current_site = get_current_site(request)
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                token = default_token_generator.make_token(user)
                email_body = render_to_string('userauth/password_reset/password_reset_email.html', {
                    'user': user,
                    'domain': current_site.domain,
                    'uid': uid,
                    'token': token,
                    'protocol': 'https',
                    'site_name': 'Vault Voting',
                })
                email_subject = 'Password reset on ' + current_site.domain
                email_body = strip_tags(email_body)
                from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or getattr(settings, 'EMAIL_FROM_ADDRESS', 'noreply@vault.local')
                try:
                    send_mail(
                        email_subject, email_body,
                        from_email=from_email,
                        recipient_list=[user.email],
                        fail_silently=True,
                    )
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).warning('Password reset email failed for %s: %s', email, e)
            except CustomUser.DoesNotExist:
                pass
            return redirect('userauth:password_reset_done')
    else:
        form = PasswordResetForm()
    return render(request, 'userauth/password_reset/form.html', {'form': form})


@csrf_protect
def password_reset_done(request):
    """Shown after user submits email: 'Check your email'."""
    return render(request, 'userauth/password_reset/done.html')


@csrf_protect
def password_reset_complete(request):
    """Shown after user has set a new password: 'Password reset complete'."""
    return render(request, 'userauth/password_reset/complete.html')


@csrf_protect
def reset_password_confirm(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = CustomUser.objects.get(pk=uid)
    except (CustomUser.DoesNotExist, TypeError, ValueError, OverflowError):
        user = None
    if user is not None and default_token_generator.check_token(user, token):
        if request.method == 'POST':
            form = SetPasswordForm(user, request.POST)
            if form.is_valid():
                form.save()
                login(request, user, backend='userauth.backends.EmailBackend')
                return redirect('userauth:password_reset_complete')
        else:
            form = SetPasswordForm(user)
        return render(request, 'userauth/password_reset/confirm.html', {'form': form, 'validlink': True})
    return render(request, 'userauth/password_reset/confirm.html', {'validlink': False})


@login_required
def mfa_setup(request):
    user = request.user
    if request.method == 'POST':
        if user.verify_mfa_token(request.POST.get('token')):
            user.mfa_enabled = True
            user.save()
            SecurityLog.objects.create(
                user=user, action_type='mfa_enabled',
                description='MFA enabled', ip_address=request.META.get('REMOTE_ADDR'), success=True
            )
            messages.success(request, 'Two-factor authentication is now active.')
            return redirect('voting:dashboard')
        messages.error(request, 'Invalid code. Try again.')
    if not user.mfa_secret:
        user.enable_mfa()
        user.mfa_enabled = False
        user.save()
    return render(request, 'userauth/mfa_setup.html', {
        'qr_code': user.get_mfa_qr_code(), 'mfa_secret': user.mfa_secret, 'user': user,
    })


def mfa_verify(request):
    token = request.POST.get('mfa_session_token') or request.GET.get('token')
    if not token:
        return redirect('userauth:login')
    try:
        mfa_session = MFASession.objects.get(session_token=token, is_verified=False)
    except MFASession.DoesNotExist:
        messages.error(request, 'Session expired. Please log in again.')
        return redirect('userauth:login')
    if mfa_session.is_expired():
        messages.error(request, 'MFA session expired.')
        return redirect('userauth:login')
    if request.method == 'POST':
        user = mfa_session.user
        use_backup = request.POST.get('use_backup_code')
        verified = False
        if use_backup:
            code = (request.POST.get('backup_code') or '').strip()
            if code and user.verify_backup_code(code):
                verified = True
        elif user.verify_mfa_token(request.POST.get('token')):
            verified = True
        if verified:
            mfa_session.is_verified = True
            mfa_session.save()
            login(request, user, backend='userauth.backends.EmailBackend')
            request.session['last_mfa_verify_ts'] = timezone.now().timestamp()
            SecurityLog.objects.create(
                user=user, action_type='login',
                description='MFA login successful',
                ip_address=request.META.get('REMOTE_ADDR'), success=True
            )
            pending_ballot = request.session.pop('vote_after_mfa', None)
            if pending_ballot:
                return redirect('voting:vote_ballot', pk=pending_ballot)
            login_next = request.session.pop('login_next', None)
            if login_next:
                allowed = {request.get_host(), *getattr(settings, 'ALLOWED_HOSTS', [])}
                if url_has_allowed_host_and_scheme(login_next, allowed_hosts=allowed, require_https=not settings.DEBUG):
                    return redirect(login_next)
            return redirect('voting:dashboard')
        messages.error(request, 'Invalid code.')
    return render(request, 'userauth/mfa_verify.html', {'mfa_session_token': token})


@login_required
def mfa_disable(request):
    if request.method == 'POST':
        if request.user.check_password(request.POST.get('password')):
            request.user.disable_mfa()
            SecurityLog.objects.create(
                user=request.user, action_type='mfa_disabled',
                description='MFA disabled', ip_address=request.META.get('REMOTE_ADDR'), success=True
            )
            messages.success(request, 'Two-factor authentication disabled.')
            return redirect('voting:dashboard')
        messages.error(request, 'Incorrect password.')
    return render(request, 'userauth/mfa_setup.html', {'disabling': True})


@login_required
def profile(request):
    from .forms import ProfileUpdateForm
    form = ProfileUpdateForm(request.POST or None, request.FILES or None, instance=request.user)
    if request.method == 'POST' and form.is_valid():
        # Check if phone number was changed/added
        old_phone = request.user.phone_number
        new_phone = form.cleaned_data.get('phone_number')
        form.save()
        user = request.user
        if not (user.nickname or '').strip() and (user.first_name or '').strip():
            user.nickname = (user.first_name or '').strip()
            user.save(update_fields=['nickname'])
        # If phone number was added or changed, trigger verification
        if new_phone and new_phone != old_phone:
            from .models import SecurityLog
            # Reset phone verification status when phone number changes
            user.phone_verified = False
            user.phone_otp = None
            user.phone_otp_created_at = None
            user.save(update_fields=['phone_verified', 'phone_otp', 'phone_otp_created_at'])
            SecurityLog.objects.create(
                user=user,
                action_type='phone_number_updated',
                description=f'Phone number updated to {new_phone[:4]}****',
                ip_address=request.META.get('REMOTE_ADDR'),
                success=True,
            )            
            messages.info(request, 'Phone number added. Please verify it to enable phone-based security features.')
            return redirect('userauth:phone_verify')
        messages.success(request, 'Profile updated.')
        return redirect('userauth:profile')
    return render(request, 'userauth/profile.html', {'form': form})


def about(request):
    return render(request, 'userauth/about.html')


def help_center(request):
    return render(request, 'userauth/help.html')


def contact(request):
    from .forms import ContactForm
    form = ContactForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        messages.success(request, 'Message sent.')
        return redirect('userauth:contact')
    return render(request, 'userauth/contact.html', {'form': form})


def privacy_policy(request):
    return render(request, 'userauth/privacy.html')


def terms_of_service(request):
    return render(request, 'userauth/terms.html')


def faq(request):
    return render(request, 'userauth/faq.html')


@login_required
@csrf_protect
def phone_verify(request):
    user = request.user
    if not user.phone_number:
        messages.error(request, 'No phone number on your account. Please update your profile.')
        return redirect('userauth:profile')
    if not user.phone_otp or (user.phone_otp_created_at and timezone.now() > user.phone_otp_created_at + timezone.timedelta(minutes=10)):
        otp = user.generate_phone_otp()
        email_sent = False
        if user.email:
            email_sent = _send_phone_otp_email_sync(user.email, otp)
        sms_result = {'sms_sent': False, 'sms_error_code': None, 'sms_error_message': ''}
        try:
            sms_result = _dispatch_phone_otp_sms(user.phone_number, otp)
        except Exception as e:
            logging.getLogger(__name__).warning('OTP SMS dispatch failed (email already sent): %s', e)
        phone_preview = (user.phone_number or '')[:4]
        sms_sent = bool(sms_result.get('sms_sent'))
        if sms_sent and email_sent:
            channels = 'phone and email'
        elif sms_sent:
            channels = 'phone'
        elif email_sent:
            channels = 'email'
        else:
            channels = 'none'
        SecurityLog.objects.create(
            user=user,
            action_type='phone_otp_sent',
            description=(
                f'OTP dispatch via {channels} to {phone_preview}****'
                + (
                    f' (sms_error_code={sms_result.get("sms_error_code")})'
                    if sms_result.get('sms_error_code')
                    else ''
                )
            ),
            ip_address=request.META.get('REMOTE_ADDR'),
            success=bool(sms_sent or email_sent),
        )
        if sms_sent and email_sent:
            messages.info(request, 'Verification code sent. Check your email for the OTP and your phone SMS.')
        elif sms_sent:
            messages.info(request, 'Verification code sent to your phone.')
        elif email_sent:
            if sms_result.get('sms_error_code') == 21608:
                messages.warning(request, 'SMS blocked by Twilio trial account for this number. Use the email OTP, then verify this phone in Twilio to enable SMS.')
            else:
                messages.warning(request, 'SMS delivery failed. Use the code sent to your email.')
        elif user.email:
            messages.warning(request, 'Verification code could not be sent by SMS, and email delivery could not be confirmed right now.')
        else:
            messages.error(request, 'Verification code could not be sent by SMS. Please try again later or update your profile email for fallback delivery.')
    if request.method == 'POST':
        code = request.POST.get('otp_code', '').strip()
        if user.verify_phone_otp(code):
            request.session.pop('dev_otp_show', None)
            SecurityLog.objects.create(
                user=user,
                action_type='phone_verified',
                description='Phone number verified via OTP',
                ip_address=request.META.get('REMOTE_ADDR'),
                success=True,
            )
            messages.success(request, 'Phone number verified successfully.')
            pending_ballot = request.session.pop('vote_after_mfa', None)
            if pending_ballot:
                return redirect('voting:vote_ballot', pk=pending_ballot)
            return redirect('userauth:profile')
        else:
            messages.error(request, 'Invalid or expired code. Please try again.')
    dev_otp = None
    if getattr(settings, 'DEBUG', False):
        dev_otp = request.session.get('dev_otp_show')
    return render(request, 'userauth/phone_verify.html', {'user': user, 'dev_otp': dev_otp})


def _send_phone_otp_email_sync(recipient_email, otp_code):
    if not recipient_email or '@' not in recipient_email:
        return False
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or getattr(settings, 'EMAIL_FROM_ADDRESS', 'noreply@vault.local')
    try:
        sent_count = send_mail(
            subject='Vault: Your phone verification code',
            message=(
                f'Your verification code is: {otp_code}\n\n'
                f'Expires in 10 minutes. If you did not request this, please ignore.'
            ),
            from_email=from_email,
            recipient_list=[recipient_email],
            fail_silently=False,
        )
        return sent_count > 0
    except Exception as exc:
        logging.getLogger(__name__).warning('OTP email send failed for %s: %s', recipient_email, exc)
        return False


def _dispatch_phone_otp_sms(phone_number, otp_code):
    kwargs = {'phone_number': phone_number, 'otp_code': otp_code, 'recipient_email': None}
    if getattr(settings, 'PHONE_OTP_SYNC_SEND', True):
        result = send_phone_otp.apply(kwargs=kwargs)
        payload = result.result if hasattr(result, 'result') else None
        if isinstance(payload, dict):
            return payload
        return {'sms_sent': False, 'sms_error_code': None, 'sms_error_message': 'Unknown SMS result'}
    send_phone_otp.delay(phone_number, otp_code, recipient_email=None)
    return {'sms_sent': True, 'sms_error_code': None, 'sms_error_message': ''}


@ratelimit(key='ip', rate='10/h', method='GET', block=False)
@login_required
def send_phone_otp_view(request):
    user = request.user
    if getattr(request, 'ratelimited', False):
        messages.warning(request, 'Too many code requests. Try again later.')
        return redirect('userauth:phone_verify')
    if not user.phone_number or not (user.phone_number or '').strip():
        messages.error(request, 'No phone number on your account. Please update your profile.')
        return redirect('userauth:profile')
    otp = user.generate_phone_otp()
    # Always send OTP by email synchronously so user gets the code even if Celery/Twilio is down
    email_sent = False
    if user.email:
        email_sent = _send_phone_otp_email_sync(user.email, otp)
    # In development, always expose the current OTP in session for the debug panel.
    if getattr(settings, 'DEBUG', False):
        request.session['dev_otp_show'] = otp
    # Dispatch SMS (sync by default; can be async via PHONE_OTP_SYNC_SEND=False)
    sms_result = {'sms_sent': False, 'sms_error_code': None, 'sms_error_message': ''}
    try:
        sms_result = _dispatch_phone_otp_sms(user.phone_number, otp)
    except Exception as e:
        logging.getLogger(__name__).warning('OTP SMS dispatch failed (email already sent): %s', e)
    phone_preview = (user.phone_number or '')[:4]
    sms_sent = bool(sms_result.get('sms_sent'))
    if sms_sent and email_sent:
        channels = 'phone and email'
    elif sms_sent:
        channels = 'phone'
    elif email_sent:
        channels = 'email'
    else:
        channels = 'none'
    SecurityLog.objects.create(
        user=user,
        action_type='phone_otp_sent',
        description=(
            f'OTP dispatch via {channels} to {phone_preview}****'
            + (
                f' (sms_error_code={sms_result.get("sms_error_code")})'
                if sms_result.get('sms_error_code')
                else ''
            )
        ),
        ip_address=request.META.get('REMOTE_ADDR'),
        success=bool(sms_sent or email_sent),
    )
    if sms_sent and email_sent:
        messages.info(
            request,
            'Verification code sent. Check your email for the OTP and your phone SMS.',
        )
    elif sms_sent:
        messages.info(
            request,
            'Verification code sent to your phone.',
        )
    elif email_sent:
        if sms_result.get('sms_error_code') == 21608:
            messages.warning(
                request,
                'SMS blocked by Twilio trial account for this number. Use the email OTP, then verify this phone in Twilio to enable SMS.',
            )
        else:
            messages.warning(
                request,
                'SMS delivery failed. Use the code sent to your email.',
            )
    elif user.email:
        messages.warning(
            request,
            'Verification code could not be sent by SMS, and email delivery could not be confirmed right now.',
        )
    else:
        messages.error(
            request,
            'Verification code could not be sent by SMS. Please try again later or update your profile email for fallback delivery.',
        )
    return redirect('userauth:phone_verify')


@ratelimit(key='ip', rate='10/h', method='POST', block=False)
@csrf_protect
def resend_verification(request):
    """Resend email verification code for inactive accounts."""
    if request.method == 'GET':
        prefilled = request.GET.get('email', '')
        return render(request, 'userauth/resend_verification.html', {'email': prefilled})
    if getattr(request, 'ratelimited', False):
        messages.error(request, 'Too many requests. Try again later.')
        return redirect('userauth:resend_verification')
    email = (request.POST.get('email') or '').strip()
    if not email:
        messages.error(request, 'Please enter your email address.')
        return render(request, 'userauth/resend_verification.html', {'email': email})
    normalized = CustomUser.objects.normalize_email(email)
    try:
        user = CustomUser.objects.get(email__iexact=normalized)
    except CustomUser.DoesNotExist:
        messages.info(request, 'No account found with this email. You can sign up instead.')
        return redirect('userauth:resend_verification')
    if user.is_active:
        messages.success(request, 'This account is already verified. You can log in.')
        return redirect('userauth:login')
    verification, _ = EmailVerification.objects.get_or_create(
        user=user,
        defaults={'code': '000000'},
    )
    verification.code = verification.generate_code()
    verification.expires_at = timezone.now() + timezone.timedelta(hours=24)
    verification.is_used = False
    verification.attempts = 0
    verification.save()
    current_site = get_current_site(request)
    message = render_to_string('userauth/account_activation.html', {
        'user': user,
        'gen_code': verification.code,
        'domain': current_site.domain,
    })
    try:
        send_mail(
            'Verify Your Email Address',
            strip_tags(message),
            getattr(settings, 'DEFAULT_FROM_EMAIL', getattr(settings, 'EMAIL_FROM_ADDRESS', 'noreply@example.com')),
            [user.email],
            html_message=message,
            fail_silently=False,
        )
    except Exception as e:
        # Log email error but don't fail the process
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f'Failed to resend verification email to {user.email}: {e}')
        # In production with console backend, email will be printed to logs
        
    messages.success(request, 'A new verification code has been sent. Check your email or use the code below.')
    
    # Show the verification code in the message for immediate access
    messages.info(request, f'Your verification code is: {verification.code}')
    return redirect('userauth:email_verification')


@ratelimit(key='ip', rate='20/h', method='POST', block=False)
@csrf_protect
def email_verification(request):
    if getattr(request, 'ratelimited', False):
        messages.error(request, 'Too many verification attempts. Try again later.')
        return render(request, 'userauth/email_verification.html')
    if request.method == 'POST':
        code = request.POST.get('code', '').strip()
        if not code:
            messages.error(request, 'Please enter the verification code.')
            return render(request, 'userauth/email_verification.html')
        try:
            verification = EmailVerification.objects.get(code=code)
        except EmailVerification.DoesNotExist:
            messages.error(request, 'Invalid code.')
            return render(request, 'userauth/email_verification.html')
        if verification.is_expired():
            messages.error(request, 'Code expired.')
            return render(request, 'userauth/email_verification.html')
        if not verification.can_attempt():
            messages.error(request, 'Too many attempts.')
            return render(request, 'userauth/email_verification.html')
        user = verification.user
        user.is_active = True
        user.is_verified = True
        user.save()
        verification.is_used = True
        verification.save()
        if not request.session.session_key:
            request.session.create()
        login(request, user, backend='userauth.backends.EmailBackend')
        messages.success(request, 'Your account has been successfully verified!')
        return redirect('voting:dashboard')
    return render(request, 'userauth/email_verification.html')

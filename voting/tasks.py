import logging
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from .models import EligibleVoter
from django.contrib.auth import get_user_model
from userauth.models import SecurityLog


logger = logging.getLogger(__name__)


def _send_sms(phone_number, body):
    """Send SMS via Twilio. Returns True if sent, False otherwise."""
    phone_number = (phone_number or '').strip().replace(' ', '')
    if not phone_number:
        return False
    if not phone_number.startswith('+'):
        phone_number = '+' + phone_number
    sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '') or ''
    token = getattr(settings, 'TWILIO_AUTH_TOKEN', '') or ''
    from_num = getattr(settings, 'TWILIO_PHONE_NUMBER', '') or ''
    if not (sid and token and from_num):
        logger.debug('Twilio not configured; skipping SMS')
        return False
    try:
        from twilio.rest import Client
        client = Client(sid, token)
        client.messages.create(body=body, from_=from_num, to=phone_number)
        logger.info('SMS sent to %s****', phone_number[:6] if len(phone_number) >= 6 else '***')
        return True
    except Exception as e:
        logger.warning('Twilio SMS failed: %s', e)
        return False


@shared_task
def send_voter_invite_notification(eligible_voter_id, invite_url):
    User = get_user_model()
    try:
        ev = EligibleVoter.objects.select_related('election').get(pk=eligible_voter_id)
    except EligibleVoter.DoesNotExist:
        logger.warning('EligibleVoter %s not found for invite notification', eligible_voter_id)
        return
    election_title = ev.election.title
    email = ev.email
    from_email = getattr(settings, 'EMAIL_FROM_ADDRESS', 'noreply@vault.local')
    subject = f'You\'re invited to vote — {election_title}'
    message = (
        f'You have been invited to vote in the election: {election_title}\n\n'
        f'Use your personal link below to sign in and vote. You must use the same email address as this invite.\n\n'
        f'{invite_url}\n\n'
        f'If you do not have an account, you can create one when you open the link.\n\n'
        f'— Vault Voting'
    )
    email_sent = False
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=[email],
            fail_silently=True,
        )
        email_sent = True
        logger.info('Invite email sent to %s for election %s', email, election_title)
    except Exception as e:
        logger.warning('Invite email failed for %s: %s', email, e)

    user = None
    sms_sent = False
    try:
        user = User.objects.filter(email__iexact=email).first()
        if user and getattr(user, 'phone_number', None) and (user.phone_number or '').strip():
            sms_body = f'Vault Voting: You\'re invited to vote in {election_title}. Open this link to vote: {invite_url}'
            if len(sms_body) > 1600:
                sms_body = f'Vault Voting: You\'re invited to vote. Link: {invite_url}'
            sms_sent = _send_sms(user.phone_number, sms_body)
    except Exception as e:
        logger.warning('Invite SMS lookup/send failed for %s: %s', email, e)

    SecurityLog.objects.create(
        user=user,
        action_type='invite_sent',
        description=f'Invite sent to {email} for {election_title} (email={"yes" if email_sent else "no"}, sms={"yes" if sms_sent else "no"})',
        ip_address=None,
        success=email_sent or sms_sent,
    )


@shared_task
def send_share_link_to_recipients(share_url, election_title, emails=None, phone_numbers=None):
    """
    Send the shareable voting link to multiple emails and/or phone numbers.
    emails and phone_numbers are lists of strings (one per recipient).
    """
    emails = emails or []
    phone_numbers = phone_numbers or []
    from_email = getattr(settings, 'EMAIL_FROM_ADDRESS', 'noreply@vault.local')
    subject = f'Voting link — {election_title}'
    message = (
        f'You are receiving a link to vote in: {election_title}\n\n'
        f'Open the link below to view the election and cast your vote.\n\n'
        f'{share_url}\n\n'
        f'— Vault Voting'
    )
    sms_body = f'Vault Voting: {election_title}. Vote here: {share_url}'
    if len(sms_body) > 1600:
        sms_body = f'Vault Voting: {election_title}. Link: {share_url}'

    email_count = 0
    for addr in emails:
        addr = (addr or '').strip().lower()
        if not addr or '@' not in addr:
            continue
        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=from_email,
                recipient_list=[addr],
                fail_silently=True,
            )
            email_count += 1
            logger.info('Share link email sent to %s for %s', addr, election_title)
        except Exception as e:
            logger.warning('Share link email failed for %s: %s', addr, e)
    sms_count = 0
    for phone in phone_numbers:
        if _send_sms(phone, sms_body):
            sms_count += 1

    return {'emails_sent': email_count, 'sms_sent': sms_count}


@shared_task
def send_vote_confirmation_email(voter_email, election_title, receipt_code):
    send_mail(
        subject=f'Vote Confirmed — {election_title}',
        message=(
            f'Your vote has been recorded.\n\n'
            f'Election: {election_title}\n'
            f'Receipt Code: {receipt_code}\n\n'
            f'Keep this code — you can use it at any time to verify your vote '
            f'was counted without revealing how you voted.'
        ),
        from_email=getattr(settings, 'EMAIL_FROM_ADDRESS', 'noreply@vault.local'),
        recipient_list=[voter_email],
        fail_silently=True,
    )


def _send_phone_otp_email(recipient_email, otp_code):
    """Send OTP to email (used as fallback and always when recipient_email is set)."""
    try:
        send_mail(
            subject='Vault: Your phone verification code',
            message=(
                f'Your verification code is: {otp_code}\n\n'
                f'Expires in 10 minutes. If you did not request this, please ignore.'
            ),
            from_email=getattr(settings, 'EMAIL_FROM_ADDRESS', 'noreply@vault.local'),
            recipient_list=[recipient_email],
            fail_silently=True,
        )
        logger.info('Phone OTP email sent to %s', recipient_email)
        return True
    except Exception as e:
        logger.warning('Phone OTP email failed: %s', e)
        return False


@shared_task
def send_phone_otp(phone_number, otp_code, recipient_email=None):
    """
    Send OTP via Twilio SMS and always via email when recipient_email is provided,
    so the user receives the code by at least one channel (phone and/or email).
    """
    phone_number = (phone_number or '').strip().replace(' ', '')
    if not phone_number.startswith('+'):
        phone_number = '+' + phone_number
    sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '') or ''
    token = getattr(settings, 'TWILIO_AUTH_TOKEN', '') or ''
    from_num = getattr(settings, 'TWILIO_PHONE_NUMBER', '') or ''
    sms_sent = False
    sms_error_code = None
    sms_error_message = ''
    if sid and token and from_num:
        try:
            from twilio.rest import Client
            client = Client(sid, token)
            client.messages.create(
                body=f'Vault Voting: Your verification code is {otp_code}. Expires in 10 minutes.',
                from_=from_num,
                to=phone_number,
            )
            sms_sent = True
            logger.info('Phone OTP SMS sent to %s', phone_number[:6] + '****')
        except Exception as e:
            sms_error_code = getattr(e, 'code', None)
            sms_error_message = getattr(e, 'msg', str(e))
            if sms_error_code:
                logger.warning('Twilio SMS failed [%s]: %s', sms_error_code, sms_error_message)
            else:
                logger.warning('Twilio SMS failed: %s', sms_error_message)
    email_sent = False
    if recipient_email:
        email_sent = _send_phone_otp_email(recipient_email, otp_code)
    if not sms_sent and not recipient_email:
        logger.warning('Phone OTP not sent: Twilio failed and no recipient_email')
    return {
        'sms_sent': sms_sent,
        'sms_error_code': sms_error_code,
        'sms_error_message': sms_error_message,
        'email_sent': email_sent,
    }


@shared_task
def auto_close_expired_elections():
    from django.utils import timezone
    from .models import Election
    count = Election.objects.filter(
        status='active', end_date__lt=timezone.now()
    ).update(status='closed')
    return f'Closed {count} elections'


@shared_task
def calculate_election_results_async(election_id):
    from .models import Election, ElectionResult
    election = Election.objects.get(pk=election_id)
    result, _ = ElectionResult.objects.get_or_create(election=election)
    result.calculate_results()
    return f'Results calculated for {election.title}'


@shared_task
def flag_suspicious_voting_activity(election_id):
    from .models import Vote, Election
    from userauth.models import SecurityLog
    from django.db.models import Count
    election = Election.objects.get(pk=election_id)
    suspicious_ips = list(
        Vote.objects.filter(election=election)
        .values('ip_address')
        .annotate(voter_count=Count('voter', distinct=True))
        .filter(voter_count__gt=3)
    )
    for entry in suspicious_ips:
        SecurityLog.objects.create(
            user=None,
            action_type='suspicious_ip',
            description=(
                f'IP {entry["ip_address"]} cast votes for {entry["voter_count"]} '
                f'different voters in election {election.title}'
            ),
            ip_address=entry['ip_address'],
            success=False,
        )
    return f'Flagged {len(suspicious_ips)} suspicious IPs'

from celery import Celery
import os
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'engine.settings')

app = Celery('voting_system')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')

@app.task
def send_email_notification(user_email, subject, message):
    from django.core.mail import send_mail
    try:
        send_mail(
            subject,
            message,
            settings.EMAIL_FROM_ADDRESS,
            [user_email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        return False

@app.task
def send_sms_notification(phone_number, message):
    from twilio.rest import Client
    try:
        account_sid = settings.TWILIO_ACCOUNT_SID
        auth_token = settings.TWILIO_AUTH_TOKEN
        client = Client(account_sid, auth_token)
        
        message = client.messages.create(
            body=message,
            from_=settings.TWILIO_PHONE_NUMBER,
            to=phone_number
        )
        return True
    except Exception as e:
        return False

@app.task
def process_vote_encryption(vote_id):
    from voting.models import Vote
    try:
        vote = Vote.objects.get(id=vote_id)
        vote.generate_verification_hash()
        return True
    except Vote.DoesNotExist:
        return False

@app.task
def calculate_election_results(election_id):
    from voting.models import ElectionResult, Election
    try:
        election = Election.objects.get(id=election_id)
        result, created = ElectionResult.objects.get_or_create(election=election)
        result.calculate_results()
        return True
    except Election.DoesNotExist:
        return False

@app.task
def audit_log_security_event(user_id, action_type, description, ip_address, user_agent):
    from userauth.models import SecurityLog
    try:
        from userauth.models import CustomUser
        user = CustomUser.objects.get(id=user_id) if user_id else None
        
        SecurityLog.objects.create(
            user=user,
            action_type=action_type,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent
        )
        return True
    except Exception as e:
        return False

@app.task
def cleanup_expired_sessions():
    from django.contrib.sessions.models import Session
    from django.utils import timezone
    import datetime
    
    expired_time = timezone.now() - datetime.timedelta(hours=24)
    expired_sessions = Session.objects.filter(expire_date__lt=expired_time)
    count = expired_sessions.count()
    expired_sessions.delete()
    return count

@app.task
def backup_election_data(election_id):
    from voting.models import Election, Vote, ElectionResult
    import json
    from django.core.files.base import ContentFile
    from io import BytesIO
    
    try:
        election = Election.objects.get(id=election_id)
        
        backup_data = {
            'election': {
                'id': str(election.id),
                'title': election.title,
                'description': election.description,
                'election_type': election.election_type,
                'voting_type': election.voting_type,
                'status': election.status,
                'start_date': election.start_date.isoformat(),
                'end_date': election.end_date.isoformat(),
                'created_at': election.created_at.isoformat(),
            },
            'votes': [],
            'backup_timestamp': timezone.now().isoformat()
        }
        
        votes = Vote.objects.filter(election=election)
        for vote in votes:
            backup_data['votes'].append({
                'id': str(vote.id),
                'ballot_id': str(vote.ballot.id),
                'voter_id': str(vote.voter.id),
                'cast_at': vote.cast_at.isoformat(),
                'selection_hash': vote.selection_hash,
                'verification_hash': vote.verification_hash,
            })
        
        backup_json = json.dumps(backup_data, indent=2)
        backup_file = ContentFile(backup_json.encode(), f'election_backup_{election_id}_{timezone.now().strftime("%Y%m%d_%H%M%S")}.json')
        
        return True
    except Exception as e:
        return False

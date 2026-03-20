from django.db import models
from django.conf import settings
import uuid
from PIL import Image
from django.core.files.uploadedfile import InMemoryUploadedFile
import sys
from io import BytesIO
from http.client import HTTPResponse
from django.utils import timezone
from datetime import timedelta
from cryptography.fernet import Fernet
from django.core.exceptions import ValidationError
import json
import hashlib


class Organisation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=250)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to='org_logos', blank=True, null=True)
    website = models.URLField(blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='owned_organisations',)
    max_elections = models.IntegerField(default=10)
    max_voters_per_election = models.IntegerField(default=1000)
    max_admins = models.IntegerField(default=5)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def election_count(self):
        return self.elections.count()

    def active_election_count(self):
        return self.elections.filter(status='active').count()

    def member_count(self):
        return self.memberships.filter(is_active=True).count()


class OrgMembership(models.Model):
    MEMBERSHIP_ROLES = [
        ('org_admin', 'Organisation Admin'),
        ('org_member', 'Organisation Member'),
        ('org_viewer', 'Organisation Viewer'),
    ]
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE,related_name='memberships',)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='org_memberships',)
    role = models.CharField(max_length=20, choices=MEMBERSHIP_ROLES, default='org_member')
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='sent_invites',)
    joined_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [['organisation', 'user']]

    def __str__(self):
        return f"{self.user.email} in {self.organisation.name} ({self.role})"


class Election(models.Model):
    ELECTION_TYPES = [
        ('local', 'Local Election'),
        ('state', 'State Election'),
        ('national', 'National Election'),
        ('primary', 'Primary Election'),
        ('general', 'General Election'),
        ('special', 'Special Election'),
    ]
    
    VOTING_TYPES = [
        ('single_choice', 'Single Choice'),
        ('multiple_choice', 'Multiple Choice'),
        ('ranked_choice', 'Ranked Choice'),
        ('proportional', 'Proportional Representation'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('active', 'Active'),
        ('closed', 'Closed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=250)
    description = models.TextField()
    election_type = models.CharField(max_length=20, choices=ELECTION_TYPES)
    voting_type = models.CharField(max_length=20, choices=VOTING_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    results_publish_date = models.DateTimeField(null=True, blank=True)
    min_age = models.IntegerField(default=18)
    citizenship_required = models.BooleanField(default=True)
    residency_required = models.BooleanField(default=True)
    voter_registration_required = models.BooleanField(default=True)
    require_mfa = models.BooleanField(default=True)
    require_google_auth = models.BooleanField(default=False)
    allow_vote_changes = models.BooleanField(default=False)
    max_vote_changes = models.IntegerField(default=0)
    allowed_email_domains = models.JSONField(
        default=list, blank=True,
        help_text='If set, only these email domains can vote. E.g. ["company.com"]',
    )
    require_voter_registration = models.BooleanField(
        default=False,
        help_text='If True, only voters on the EligibleVoter invite list can vote.',
    )
    require_captcha = models.BooleanField(default=True)
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    organisation = models.ForeignKey(
        Organisation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='elections',
    )
    tenant = models.ForeignKey(
        'userauth.Tenant', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='elections', help_text='Tenant/organization; null = platform-wide.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    version = models.IntegerField(default=1)
    brand_name = models.CharField(max_length=120, blank=True, null=True, help_text='Display name for this election; defaults to title if blank.')
    primary_color = models.CharField(max_length=7, blank=True, null=True, help_text='Hex color e.g. #B45309 for accents; used in election-specific pages.')
    logo = models.ImageField(upload_to='election_logos', blank=True, null=True)
    header_img = models.ImageField(upload_to='election_headers', blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'start_date']),
            models.Index(fields=['election_type']),
        ]
    
    def __str__(self):
        return self.title
    
    def clean(self):
        if self.start_date >= self.end_date:
            raise ValidationError('End date must be after start date')
        if self.results_publish_date and self.results_publish_date <= self.end_date:
            raise ValidationError('Results publish date must be after end date')
    
    def is_active(self):
        now = timezone.now()
        return self.status == 'active' and self.start_date <= now <= self.end_date

    def has_ended(self):
        return timezone.now() > self.end_date
    
    def can_vote(self, user):
        if not self.is_active():
            return False
        if getattr(self, 'creator_id', None) is not None and user.pk == self.creator_id:
            return False  # Creator cannot vote in their own election
        if not user.is_eligible_voter():
            return False
        if self.min_age > user.age:
            return False
        if self.citizenship_required and not user.is_citizen:
            return False
        return True

    def get_admins(self):
        admins = [self.creator]
        if self.organisation_id:
            qs = self.organisation.memberships.filter(is_active=True, role='org_admin').select_related('user')
            admins.extend(m.user for m in qs)
        seen = set()
        unique_admins = []
        for u in admins:
            if not u:
                continue
            if u.pk in seen:
                continue
            seen.add(u.pk)
            unique_admins.append(u)
        return unique_admins

    def user_can_manage(self, user):
        if not user.is_authenticated:
            return False
        if getattr(user, 'role', None) == 'super_admin':
            return True
        if user == self.creator:
            return True
        if getattr(user, 'role', None) == 'org_admin' and self.organisation_id:
            return self.organisation.memberships.filter(user=user, is_active=True).exists()
        return False

    def user_can_view(self, user):
        if self.user_can_manage(user):
            return True
        return False
    
    def process_image(self, image_field, desired_size, format='PNG', quality=90):
        if not image_field:
            return HTTPResponse(status=204)
        img = Image.open(image_field)
        img.thumbnail(desired_size)
        width, height = img.size
        left = (width - desired_size[0]) / 2
        top = (height - desired_size[1]) / 2
        right = (width + desired_size[0]) / 2
        bottom = (height + desired_size[1]) / 2
        img = img.crop((left, top, right, bottom))
        img_output = BytesIO()
        img = img.convert("RGB")
        img.save(img_output, format=format, quality=quality)
        img_output.seek(0)
        extension = f"{image_field.name.split('.')[0]}_cropped.{format.lower()}"
        processed_image = InMemoryUploadedFile(
            img_output, 'ImageField', extension, f'image/{format.lower()}',
            sys.getsizeof(img_output), None
        )
        return processed_image
    
    def save(self, *args, **kwargs):
        if hasattr(self, 'header_img') and self.header_img:
            self.header_img = self.process_image(self.header_img, (600, 400))
        if hasattr(self, 'logo') and self.logo:
            self.logo = self.process_image(self.logo, (200, 100))
        super().save(*args, **kwargs)


class Ballot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name='ballots')
    title = models.CharField(max_length=250)
    description = models.TextField(blank=True)
    question = models.TextField()
    max_selections = models.IntegerField(default=1)
    min_selections = models.IntegerField(default=1)
    allow_write_in = models.BooleanField(default=False)
    is_required = models.BooleanField(default=True)
    # For proportional representation: number of seats to allocate (e.g. 5 for top-5 by share). Null/1 = single winner.
    seats = models.IntegerField(null=True, blank=True, default=1, help_text='For PR: number of seats to allocate. Default 1.')
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['order', 'title']
        unique_together = ['election', 'order']

    def _next_free_order(self, election_id, exclude_pk=None):
        qs = Ballot.objects.filter(election_id=election_id)
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        used = set(qs.values_list('order', flat=True))
        n = 0
        while n in used:
            n += 1
        return n

    def save(self, *args, **kwargs):
        from django.db import IntegrityError
        election_id = getattr(self, 'election_id', None) or (getattr(self, 'election', None) and self.election.pk)
        if election_id is not None:
            if self._state.adding:
                self.order = self._next_free_order(election_id)
            else:
                if Ballot.objects.filter(election_id=election_id, order=self.order).exclude(pk=self.pk).exists():
                    self.order = self._next_free_order(election_id, exclude_pk=self.pk)
        for attempt in range(5):
            try:
                super().save(*args, **kwargs)
                return
            except IntegrityError as e:
                err = str(e).lower()
                if election_id is not None and ('unique' in err or 'duplicate' in err) and 'order' in err:
                    self.order = self._next_free_order(election_id, exclude_pk=getattr(self, 'pk', None))
                    if attempt == 4:
                        raise
                else:
                    raise
    
    def __str__(self):
        return f"{self.election.title} - {self.title}"
    
    def clean(self):
        if self.min_selections > self.max_selections:
            raise ValidationError('Minimum selections cannot be greater than maximum selections')
        if self.max_selections > 10:
            raise ValidationError('Maximum selections cannot exceed 10')
        if self.seats is not None and self.seats < 1:
            raise ValidationError('Seats must be at least 1')


def _compress_candidate_photo(image_field, max_size=(400, 400), quality=85):
    """Resize candidate photo to max_size (aspect ratio preserved), save as JPEG. Returns InMemoryUploadedFile or None."""
    if not image_field:
        return None
    try:
        img = Image.open(image_field)
        img.thumbnail(max_size, Image.BICUBIC)
        img = img.convert('RGB')
        img_output = BytesIO()
        img.save(img_output, format='JPEG', quality=quality, optimize=True)
        img_output.seek(0)
        name = (image_field.name or 'photo').rsplit('.', 1)[0] + '_thumb.jpg'
        return InMemoryUploadedFile(
            img_output, 'ImageField', name, 'image/jpeg',
            img_output.getbuffer().nbytes, None
        )
    except Exception:
        return None


class Candidate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ballot = models.ForeignKey(Ballot, on_delete=models.CASCADE, related_name='candidates')
    name = models.CharField(max_length=250)
    description = models.TextField(blank=True)
    party = models.CharField(max_length=100, blank=True)
    photo = models.ImageField(upload_to='candidate_photos', blank=True, null=True)
    order = models.IntegerField(default=0)
    is_write_in = models.BooleanField(default=False)
    votes_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['order', 'name']
        unique_together = ['ballot', 'order']
    
    def __str__(self):
        return f"{self.ballot.title} - {self.name}"

    def save(self, *args, **kwargs):
        if getattr(self, 'photo', None) and hasattr(self.photo, 'read'):
            compressed = _compress_candidate_photo(self.photo)
            if compressed:
                self.photo = compressed
        super().save(*args, **kwargs)


class Vote(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    election = models.ForeignKey(Election, on_delete=models.CASCADE)
    ballot = models.ForeignKey(Ballot, on_delete=models.CASCADE)
    voter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    encrypted_selections = models.TextField()
    selection_hash = models.CharField(max_length=64)
    vote_token = models.CharField(max_length=64, unique=True)
    cast_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    is_verified = models.BooleanField(default=False)
    verification_hash = models.CharField(max_length=64, blank=True)
    
    class Meta:
        unique_together = [['ballot', 'voter']]
        indexes = [
            models.Index(fields=['election', 'cast_at']),
            models.Index(fields=['vote_token']),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise PermissionError(
                'Vote records are immutable. A vote cannot be modified after creation.'
            )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Vote by {self.voter.email} in {self.election.title}"
    
    def encrypt_selections(self, selections):
        from django.conf import settings
        key = settings.ENCRYPTION_KEY.encode()
        fernet = Fernet(key)
        json_data = json.dumps(selections)
        encrypted_data = fernet.encrypt(json_data.encode())
        self.encrypted_selections = encrypted_data.decode()
        self.selection_hash = hashlib.sha256(encrypted_data).hexdigest()
    
    def decrypt_selections(self):
        from django.conf import settings
        key = settings.ENCRYPTION_KEY.encode()
        fernet = Fernet(key)
        decrypted_data = fernet.decrypt(self.encrypted_selections.encode())
        return json.loads(decrypted_data.decode())
    
    def generate_verification_hash(self):
        """Set verification_hash. Uses update() to avoid triggering save() (immutability)."""
        data = f"{self.id}{self.election.id}{self.voter.id}{self.cast_at}"
        new_hash = hashlib.sha256(data.encode()).hexdigest()
        Vote.objects.filter(pk=self.pk).update(verification_hash=new_hash)
        self.verification_hash = new_hash


class VoteReceipt(models.Model):
    vote = models.OneToOneField(Vote, on_delete=models.CASCADE)
    receipt_code = models.CharField(max_length=32, unique=True)
    generated_at = models.DateTimeField(auto_now_add=True)

    def generate_receipt_code(self):
        import random
        import string
        chars = string.ascii_uppercase + string.digits
        return ''.join(random.choice(chars) for _ in range(32))

    def save(self, *args, **kwargs):
        if not self.receipt_code:
            self.receipt_code = self.generate_receipt_code()
        super().save(*args, **kwargs)


class EligibleVoter(models.Model):
    """Invite-only voter registration per election."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    election = models.ForeignKey(
        Election, on_delete=models.CASCADE, related_name='eligible_voters'
    )
    email = models.EmailField()
    invite_token = models.CharField(max_length=64, unique=True)
    has_voted = models.BooleanField(default=False)
    invited_at = models.DateTimeField(auto_now_add=True)
    voted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [['election', 'email']]

    def save(self, *args, **kwargs):
        if not self.invite_token:
            import secrets
            self.invite_token = secrets.token_urlsafe(48)
        super().save(*args, **kwargs)

    def mark_voted(self):
        self.has_voted = True
        self.voted_at = timezone.now()
        self.save()


class VotingSession(models.Model):
    """One active voting session per user per election."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='voting_sessions'
    )
    election = models.ForeignKey(
        Election, on_delete=models.CASCADE, related_name='voting_sessions'
    )
    session_key = models.CharField(max_length=40)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed = models.BooleanField(default=False)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        unique_together = [['user', 'election']]

    def complete(self):
        self.completed = True
        self.completed_at = timezone.now()
        self.save()


class VoteChainEntry(models.Model):
    """Append-only hash chain per ballot for vote integrity."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ballot = models.ForeignKey(
        Ballot, on_delete=models.CASCADE, related_name='chain_entries'
    )
    vote = models.OneToOneField(
        Vote, on_delete=models.CASCADE, related_name='chain_entry'
    )
    sequence_number = models.PositiveIntegerField()
    previous_hash = models.CharField(max_length=64)
    current_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sequence_number']
        unique_together = [['ballot', 'sequence_number']]

    @classmethod
    def create_for_vote(cls, vote):
        last = cls.objects.filter(ballot=vote.ballot).order_by('-sequence_number').first()
        prev_hash = last.current_hash if last else ('0' * 64)
        sequence = (last.sequence_number + 1) if last else 1
        raw = f"{prev_hash}{vote.id}{vote.voter_id}{vote.selection_hash}{vote.cast_at}"
        current_hash = hashlib.sha256(raw.encode()).hexdigest()
        return cls.objects.create(ballot=vote.ballot, vote=vote, sequence_number=sequence, previous_hash=prev_hash, current_hash=current_hash,)

    def save(self, *args, **kwargs):
        if self.pk:
            raise PermissionError('VoteChainEntry records are immutable.')
        super().save(*args, **kwargs)


class ElectionResult(models.Model):
    election = models.OneToOneField(Election, on_delete=models.CASCADE)
    total_votes = models.IntegerField(default=0)
    total_voters = models.IntegerField(default=0)
    encrypted_results = models.TextField(blank=True, default='')
    results_hash = models.CharField(max_length=64, blank=True, default='')
    published_at = models.DateTimeField(null=True, blank=True)
    is_final = models.BooleanField(default=False)
    sealed_at = models.DateTimeField(null=True, blank=True)
    public_verification_hash = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def seal(self):
        """Seal result once when election closes. Sets public_verification_hash."""
        if self.is_final:
            raise PermissionError('Election result is already sealed.')
        self.calculate_results()
        self.published_at = timezone.now()
        self.sealed_at = timezone.now()
        self.is_final = True
        raw = f"{self.election.id}{self.total_votes}{self.results_hash}{self.sealed_at.isoformat()}"
        self.public_verification_hash = hashlib.sha256(raw.encode()).hexdigest()
        self.save()

    def verify_integrity(self):
        """Return True if stored public_verification_hash still matches."""
        if not self.sealed_at:
            return False
        raw = f"{self.election.id}{self.total_votes}{self.results_hash}{self.sealed_at.isoformat()}"
        expected = hashlib.sha256(raw.encode()).hexdigest()
        return self.public_verification_hash == expected

    def calculate_results(self):
        from collections import Counter
        from .proportional import allocate_seats_largest_remainder
        votes = Vote.objects.filter(election=self.election)
        self.total_votes = votes.count()
        self.total_voters = votes.values('voter').distinct().count()
        results = {}
        election = self.election
        for ballot in election.ballots.all():
            counter = Counter()
            for vote in votes.filter(ballot=ballot):
                try:
                    for sel in vote.decrypt_selections():
                        counter[sel] += 1
                except Exception:
                    continue
            candidates = list(ballot.candidates.all())
            ballot_results = [
                {
                    'candidate_id': str(c.id),
                    'candidate_name': c.name,
                    'votes': counter.get(str(c.id), 0),
                }
                for c in candidates
            ]
            # Proportional: add seat allocation when ballot has seats > 1
            if getattr(election, 'voting_type', None) == 'proportional':
                num_seats = getattr(ballot, 'seats', None)
                if num_seats is not None and num_seats > 1:
                    candidate_votes = {str(c.id): counter.get(str(c.id), 0) for c in candidates}
                    seats_map = allocate_seats_largest_remainder(candidate_votes, num_seats)
                    for r in ballot_results:
                        r['seats'] = seats_map.get(r['candidate_id'], 0)
                else:
                    for r in ballot_results:
                        r['seats'] = 0
            results[str(ballot.id)] = {
                'ballot_title': ballot.title,
                'results': ballot_results,
            }
        from django.conf import settings
        key = settings.ENCRYPTION_KEY.encode()
        fernet = Fernet(key)
        json_data = json.dumps(results)
        encrypted_data = fernet.encrypt(json_data.encode())
        self.encrypted_results = encrypted_data.decode()
        self.results_hash = hashlib.sha256(encrypted_data).hexdigest()
        self.save()
    
    def publish_results(self):
        from django.conf import settings
        if timezone.now() >= self.election.results_publish_date:
            self.published_at = timezone.now()
            self.is_final = True
            self.save()
            return True
        return False
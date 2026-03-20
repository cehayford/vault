from datetime import timedelta
from django.utils import timezone
import random
import re
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.core.exceptions import ValidationError
from cryptography.fernet import Fernet
from django.conf import settings
import pyotp
import qrcode
from io import BytesIO
from base64 import b64encode


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_verified', True)
        extra_fields.setdefault('role', 'super_admin')
        return self.create_user(email, password, **extra_fields)


class Tenant(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=80, unique=True, allow_unicode=False)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    billing_email = models.EmailField(blank=True, null=True)
    plan = models.CharField(max_length=40, blank=True, null=True, help_text='e.g. free, pro, enterprise')

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class CustomUser(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = [
        ('voter', 'Voter'),
        ('election_admin', 'Election Administrator'),
        ('org_admin', 'Organisation Admin'),
        ('monitor', 'Monitor'),
        ('auditor', 'Auditor'),
        ('super_admin', 'Super Admin'),
    ]
    first_name = models.CharField(max_length=150, blank=True, null=True)
    last_name = models.CharField(max_length=150, blank=True, null=True)
    email = models.EmailField(unique=True)
    nickname = models.CharField(max_length=40, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.TextField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    zip_code = models.CharField(max_length=20, blank=True, null=True)
    country = models.CharField(max_length=100, default='US')

    CITIZENSHIP_COUNTRY_CHOICES = [
        ('', '-- Select country of citizenship --'),
        ('US', 'United States'),
        ('AF', 'Afghanistan'), ('AL', 'Albania'), ('DZ', 'Algeria'), ('AR', 'Argentina'), ('AU', 'Australia'),
        ('AT', 'Austria'), ('BD', 'Bangladesh'), ('BE', 'Belgium'), ('BR', 'Brazil'), ('CA', 'Canada'),
        ('CL', 'Chile'), ('CN', 'China'), ('CO', 'Colombia'), ('HR', 'Croatia'), ('CU', 'Cuba'),
        ('CZ', 'Czech Republic'), ('DK', 'Denmark'), ('EG', 'Egypt'), ('ET', 'Ethiopia'), ('FI', 'Finland'),
        ('FR', 'France'), ('DE', 'Germany'), ('GH', 'Ghana'), ('GR', 'Greece'), ('HK', 'Hong Kong'),
        ('HU', 'Hungary'), ('IN', 'India'), ('ID', 'Indonesia'), ('IR', 'Iran'), ('IQ', 'Iraq'),
        ('IE', 'Ireland'), ('IL', 'Israel'), ('IT', 'Italy'), ('JP', 'Japan'), ('KE', 'Kenya'),
        ('MY', 'Malaysia'), ('MX', 'Mexico'), ('NL', 'Netherlands'), ('NG', 'Nigeria'), ('NO', 'Norway'),
        ('PK', 'Pakistan'), ('PL', 'Poland'), ('PT', 'Portugal'), ('RO', 'Romania'), ('RU', 'Russia'),
        ('SA', 'Saudi Arabia'), ('RS', 'Serbia'), ('SG', 'Singapore'), ('ZA', 'South Africa'),
        ('KR', 'South Korea'), ('ES', 'Spain'), ('SE', 'Sweden'), ('CH', 'Switzerland'), ('TW', 'Taiwan'),
        ('TZ', 'Tanzania'), ('TH', 'Thailand'), ('TR', 'Turkey'), ('UG', 'Uganda'), ('UA', 'Ukraine'),
        ('AE', 'United Arab Emirates'), ('GB', 'United Kingdom'), ('VE', 'Venezuela'), ('VN', 'Vietnam'),
    ]
    citizenship_country = models.CharField(
        max_length=2,
        blank=True,
        null=True,
        choices=CITIZENSHIP_COUNTRY_CHOICES,
        help_text='Country of citizenship (used to prove citizenship for voting).',
    )
    is_citizen = models.BooleanField(default=False)
    voter_id = models.CharField(max_length=50, unique=True, null=True, blank=True)
    registration_date = models.DateTimeField(null=True, blank=True)
    eligibility_verified = models.BooleanField(default=False)
    eligibility_verification_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='voter')
    mfa_enabled = models.BooleanField(default=False)
    mfa_secret = models.CharField(max_length=32, blank=True, null=True)
    backup_codes = models.JSONField(default=list, blank=True)
    phone_verified = models.BooleanField(default=False)
    phone_otp = models.CharField(max_length=6, blank=True, null=True)
    phone_otp_created_at = models.DateTimeField(null=True, blank=True)
    failed_login_attempts = models.IntegerField(default=0)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    last_login_device = models.CharField(max_length=255, blank=True, null=True)
    account_locked = models.BooleanField(default=False)
    lockout_timestamp = models.DateTimeField(null=True, blank=True)
    data_consent = models.BooleanField(default=False)
    marketing_consent = models.BooleanField(default=False)
    account_created_at = models.DateTimeField(auto_now_add=True, null=True)
    last_updated = models.DateTimeField(auto_now=True)
    tenant = models.ForeignKey(
        Tenant, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='users', help_text='Organization this user belongs to; null = platform-wide.',
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    objects = CustomUserManager()

    def __str__(self):
        return self.email

    def clean(self):
        super().clean()
        if self.date_of_birth:
            from datetime import date, datetime
            dob = self.date_of_birth
            if isinstance(dob, str):
                try:
                    dob = datetime.strptime(dob[:10], '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    return
            age = date.today().year - dob.year - ((date.today().month, date.today().day) < (dob.month, dob.day))
            if age < 18:
                raise ValidationError('User must be at least 18 years old to register')

    def save(self, *args, **kwargs):
        self.is_citizen = bool(self.citizenship_country and self.citizenship_country.strip())
        super().save(*args, **kwargs)

    def enable_mfa(self):
        if not self.mfa_secret:
            self.mfa_secret = pyotp.random_base32()
            self.backup_codes = [str(random.randint(100000, 999999)) for _ in range(10)]
        self.mfa_enabled = True
        self.save()

    def disable_mfa(self):
        self.mfa_enabled = False
        self.mfa_secret = None
        self.backup_codes = []
        self.save()

    def lock_account(self):
        self.account_locked = True
        self.lockout_timestamp = timezone.now()
        self.save()

    def get_mfa_qr_code(self):
        if not self.mfa_secret:
            return None
        totp_uri = pyotp.totp.TOTP(self.mfa_secret).provisioning_uri(name=self.email, issuer_name="Secure Voting System")
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(totp_uri)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        qr_code = b64encode(buffer.getvalue()).decode()
        return qr_code

    def verify_mfa_token(self, token):
        if not self.mfa_secret:
            return False
        normalized = str(token or '').strip().replace(' ', '')
        if not normalized.isdigit():
            return False
        totp = pyotp.TOTP(self.mfa_secret)
        return bool(totp.verify(normalized, valid_window=1))

    def verify_backup_code(self, code):
        if code in self.backup_codes:
            self.backup_codes.remove(code)
            self.save()
            return True
        return False

    def generate_phone_otp(self):
        self.phone_otp = str(random.randint(100000, 999999))
        self.phone_otp_created_at = timezone.now()
        self.save()
        return self.phone_otp

    def verify_phone_otp(self, code):
        if not self.phone_otp or not self.phone_otp_created_at:
            return False
        if timezone.now() > self.phone_otp_created_at + timedelta(minutes=10):
            return False
        normalized = re.sub(r'\D', '', str(code or ''))
        if self.phone_otp != normalized:
            return False
        self.phone_verified = True
        self.phone_otp = None
        self.phone_otp_created_at = None
        self.save()
        return True

    def is_eligible_voter(self):
        return (
            self.is_active and
            self.is_verified and
            self.eligibility_verified and
            self.is_citizen and
            self.date_of_birth and
            self.age is not None and
            self.age >= 18
        )

    @property
    def age(self):
        if not self.date_of_birth:
            return None
        from datetime import date, datetime
        dob = self.date_of_birth
        if isinstance(dob, str):
            try:
                dob = datetime.strptime(dob[:10], '%Y-%m-%d').date()
            except (ValueError, TypeError):
                return None
        return date.today().year - dob.year - ((date.today().month, date.today().day) < (dob.month, dob.day))

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


class EmailVerification(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    attempts = models.IntegerField(default=0)

    def save(self, *args, **kwargs):
        if not self.pk:
            self.expires_at = timezone.now() + timedelta(hours=24)
        super().save(*args, **kwargs)

    def generate_code(self):
        return str(random.randint(100000, 999999))

    def is_expired(self):
        return timezone.now() > self.expires_at

    def can_attempt(self):
        return not self.is_used and not self.is_expired() and self.attempts < 5


class MFASession(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    session_token = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_verified = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.pk:
            self.expires_at = timezone.now() + timedelta(minutes=10)
        super().save(*args, **kwargs)

    def is_expired(self):
        return timezone.now() > self.expires_at


class SecurityLog(models.Model):
    ACTION_TYPES = [
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('login_failed', 'Login Failed'),
        ('mfa_enabled', 'MFA Enabled'),
        ('mfa_disabled', 'MFA Disabled'),
        ('password_change', 'Password Change'),
        ('account_locked', 'Account Locked'),
        ('account_unlocked', 'Account Unlocked'),
        ('phone_verified', 'Phone Verified'),
        ('phone_otp_sent', 'Phone OTP Sent'),
        ('phone_number_updated', 'Phone Number Updated'),
        ('vote_cast', 'Vote Cast'),
        ('vote_duplicate_blocked', 'Duplicate Vote Blocked'),
        ('vote_eligibility_denied', 'Eligibility Check Failed'),
        ('vote_captcha_failed', 'CAPTCHA Verification Failed'),
        ('vote_ratelimit_hit', 'Vote Rate Limit Hit'),
        ('suspicious_ip', 'Suspicious IP Activity'),
        ('election_closed', 'Election Closed'),
        ('result_published', 'Results Published'),
        ('result_accessed', 'Results Accessed'),
        ('admin_action', 'Admin Action'),
        ('role_change', 'Role Change'),
        ('invite_sent', 'Voter Invite Sent'),
        ('invite_token_used', 'Invite Token Used'),
    ]
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, null=True, blank=True)
    action_type = models.CharField(max_length=32, choices=ACTION_TYPES)
    description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    success = models.BooleanField(default=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['action_type', 'timestamp']),
        ]

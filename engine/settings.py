import os
import sys
from pathlib import Path
from decouple import config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env from project root so SECRET_KEY etc. are always available (avoids 500 from empty SECRET_KEY)
_env_file = BASE_DIR / '.env'
if _env_file.exists():
    from decouple import Config, RepositoryEnv
    _env_config = Config(RepositoryEnv(str(_env_file)))
else:
    _env_config = None

def _get_env(key, default=None):
    if _env_config is not None:
        try:
            return _env_config.get(key, default=default or '')
        except Exception:
            return os.environ.get(key, default)
    return os.environ.get(key, default)

# Legacy env() for any code that still uses it (e.g. INSTALLED_APPS overrides)
try:
    import django_environ
    _django_env = django_environ.Env()
    _django_env.Env.read_env(str(_env_file))
    env = _django_env
except ImportError:
    class _Env:
        def __call__(self, key, default=None, **kwargs):
            return _get_env(key, default)
    env = _Env()

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = _get_env('DEBUG', 'True').strip().lower() in ('1', 'true', 'yes')
RUNNING_TESTS = len(sys.argv) > 1 and sys.argv[1] == 'test'
# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = _get_env('SECRET_KEY')
_DEFAULT_INSECURE_KEY = 'django-insecure-+tnx+g%-6v$by&e($di_a%t!7+8+nc2i7s1^d5%b&@c47kw06('
if not SECRET_KEY:
    SECRET_KEY = _DEFAULT_INSECURE_KEY
if not DEBUG and SECRET_KEY == _DEFAULT_INSECURE_KEY:
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured('Set a non-default SECRET_KEY in production (e.g. in .env).')
# SECURE_SSL_REDIRECT = True
# SECURE_HSTS_SECONDS = 31536000
# SECURE_HSTS_INCLUDE_SUBDOMAINS = True
# SECURE_HSTS_PRELOAD = True
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
else:
    CSRF_COOKIE_SECURE = False
    SESSION_COOKIE_SECURE = False

# Never force HTTPS redirects in test runs; Django test client uses HTTP by default.
if RUNNING_TESTS:
    SECURE_SSL_REDIRECT = False
    CSRF_COOKIE_SECURE = False
    SESSION_COOKIE_SECURE = False

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'

# SECURITY WARNING: don't run with debug turned on in production!

# HTTPS-only in production (disable for local runserver which serves HTTP)
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
else:
    CSRF_COOKIE_SECURE = False
    SESSION_COOKIE_SECURE = False

# Silence checks when using LocMemCache (no Redis); use Redis in prod for ratelimit
SILENCED_SYSTEM_CHECKS = ['django_ratelimit.E003', 'django_ratelimit.W001']

# The duplicate HTTPS block above can re-enable redirects; enforce test-safe values last.
if RUNNING_TESTS:
    SECURE_SSL_REDIRECT = False
    CSRF_COOKIE_SECURE = False
    SESSION_COOKIE_SECURE = False

ALLOWED_HOSTS = [
    'localhost', '127.0.0.1',
    '.railway.app',
    'vault-production-4d85.up.railway.app',
]

CSRF_TRUSTED_ORIGINS = [
    'http://127.0.0.1:8000',
    'http://localhost:8000',
    'https://127.0.0.1:8000',
    'https://localhost:8000',
    'https://127.0.0.1:8443',
    'https://localhost:8443',
    'https://vault-production-4d85.up.railway.app',
]
_railway_domain = os.environ.get('RAILWAY_PUBLIC_DOMAIN')
if _railway_domain:
    CSRF_TRUSTED_ORIGINS.append(f'https://{_railway_domain}')
SESSION_COOKIE_SAMESITE = 'Strict'

# @login_required redirects here when user is not authenticated
LOGIN_URL = '/login/'

CORS_ALLOW_CREDENTIALS = True

INSTALLED_APPS = [
    'engine',  # First so runserver uses HTTPS (runserver_plus) and avoids HTTP-only errors
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party apps
    'rest_framework',
    'django_filters',
    'django_recaptcha',
    'corsheaders',
    'django_ratelimit',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    # Local apps
    'userauth',
    'voting',
    'nominee',
    # Development and utilities
    'django_extensions',
    'debug_toolbar',
    # Template libraries
    'django.contrib.humanize',
]

# EmailBackend first so login by email works (CustomUser has no username field)
AUTHENTICATION_BACKENDS = [
    'userauth.backends.EmailBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

AUTH_USER_MODEL = 'userauth.CustomUser'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
}

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',  # After Session, before Common (for request.LANGUAGE_CODE)
    'engine.middleware.EnsureSessionKeyMiddleware',  # Before login views so session_key exists for axes_accesslog
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'debug_toolbar.middleware.DebugToolbarMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'voting.middleware.Custom404Middleware',
    'allauth.account.middleware.AccountMiddleware',
]

# Rate limiting (login protection via @ratelimit on userauth.views.signin; axes removed to avoid axes_accesslog.session_hash NOT NULL on allauth /accounts/login/)
RATELIMIT_ENABLE = True
RATELIMIT_USE_CACHE = 'default'
RATELIMIT_BLOCK = True

ROOT_URLCONF = 'engine.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.i18n',
            ],
        },
    },
]

WSGI_APPLICATION = 'engine.wsgi.application'

# https://docs.djangoproject.com/en/5.2/ref/settings/#databases
# Database configuration
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        'OPTIONS': {
            'timeout': 20,
        },
    }
}

# Redis not on PythonAnywhere free tier — LocMemCache for dev; use Redis in prod for ratelimit
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

# Session configuration — DB backend (no Redis on PA free)
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
# SESSION_COOKIE_SECURE set above per DEBUG (must be False for HTTP runserver)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Strict'
SESSION_COOKIE_AGE = 1800  # 30 minutes

# Celery configuration
REDIS_URL = (_get_env('REDIS_URL', 'redis://localhost:6379/0') or 'redis://localhost:6379/0').strip()
CELERY_BROKER_URL = (_get_env('CELERY_BROKER_URL', REDIS_URL) or REDIS_URL).strip()
CELERY_RESULT_BACKEND = (_get_env('CELERY_RESULT_BACKEND', REDIS_URL) or REDIS_URL).strip()
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_BEAT_SCHEDULE = {
    'auto-close-expired-elections': {
        'task': 'voting.tasks.auto_close_expired_elections',
        'schedule': 300.0,  # every 5 minutes
    },
}

# Password hashing — Argon2 first when available (Part 15); else PBKDF2 so tests/dev work without argon2-cffi
try:
    import argon2  # noqa: F401
    PASSWORD_HASHERS = [
        'django.contrib.auth.hashers.Argon2PasswordHasher',
        'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    ]
except ImportError:
    PASSWORD_HASHERS = [
        'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    ]

# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/
LANGUAGE_CODE = 'en'

LANGUAGES = [
    ('en', 'English'),
    ('es', 'Spanish'),
    ('fr', 'French'),
]

# Where to find message files (python manage.py makemessages -l es -l fr && compilemessages)
LOCALE_PATHS = [BASE_DIR / 'locale']

# Language cookie for set_language view (persists choice)
LANGUAGE_COOKIE_NAME = 'django_language'
LANGUAGE_COOKIE_HTTPONLY = True
LANGUAGE_COOKIE_SAMESITE = 'Lax'

PARSE_DATE = ['%d-%m-%Y', '%Y-%m-%d']

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/
STATIC_URL = '/static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATIC_ROOT = os.path.join(BASE_DIR, 'local_cdn')
os.makedirs(STATIC_ROOT, exist_ok=True)
if DEBUG:
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/local_media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'local_media')

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Email settings: prefer explicit backend, otherwise SMTP when credentials are configured.
email_host = (_get_env('EMAIL_HOST', '') or '').strip() or 'smtp.gmail.com'
email_user = (
    (_get_env('EMAIL_HOST_USER', '') or '').strip()
    or (_get_env('EMAIL_USER', '') or '').strip()
    or (_get_env('EMAIL_FROM_ADDRESS', '') or '').strip()
)
email_pass = (_get_env('EMAIL_HOST_PASSWORD', '') or '').strip()
try:
    email_port = int((_get_env('EMAIL_PORT', '587') or '').strip() or '587')
except ValueError:
    email_port = 587
email_use_tls = _get_env('EMAIL_USE_TLS', 'True').strip().lower() in ('1', 'true', 'yes')
email_use_ssl = _get_env('EMAIL_USE_SSL', 'False').strip().lower() in ('1', 'true', 'yes')
try:
    email_timeout = int((_get_env('EMAIL_TIMEOUT', '10') or '').strip() or '10')
except ValueError:
    email_timeout = 10
explicit_email_backend = (_get_env('EMAIL_BACKEND', '') or '').strip()

_placeholder_email_users = {'', 'your-email@gmail.com', 'example@example.com', 'noreply@your-voting-system.com'}
_placeholder_email_passwords = {'', 'your-app-password', 'changeme'}
smtp_configured = (
    bool(email_host)
    and email_user not in _placeholder_email_users
    and email_pass not in _placeholder_email_passwords
)

if explicit_email_backend:
    EMAIL_BACKEND = explicit_email_backend
elif DEBUG:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
elif smtp_configured:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
else:
    # Keep the app functional when SMTP is missing, but no external email delivery happens.
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

EMAIL_HOST = email_host
EMAIL_PORT = email_port
EMAIL_USE_TLS = email_use_tls
EMAIL_USE_SSL = email_use_ssl
EMAIL_TIMEOUT = email_timeout
EMAIL_HOST_USER = email_user
EMAIL_HOST_PASSWORD = email_pass

SITE_ID = 1

# Only enable Google OAuth when credentials are set (avoids "Missing required parameter: client_id" from Google)
_google_client_id = (os.getenv('GOOGLE_OAUTH_CLIENT_ID') or '').strip()
GOOGLE_OAUTH_ENABLED = bool(_google_client_id)
SOCIALACCOUNT_PROVIDERS = {}
if _google_client_id:
    SOCIALACCOUNT_PROVIDERS['google'] = {
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
        'APP': {
            'client_id': _google_client_id,
            'secret': (os.getenv('GOOGLE_OAUTH_CLIENT_SECRET') or '').strip(),
            'key': '',
        },
    }

# Allauth configuration (CustomUser has USERNAME_FIELD='email', no username field)
ACCOUNT_USER_MODEL_USERNAME_FIELD = 'email'
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_EMAIL_VERIFICATION = 'optional'
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_VERIFICATION = EMAIL_HOST_USER

# Logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'voting.log',
            'formatter': 'verbose',
        },
        'security': {
            'level': 'WARNING',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'security.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
        'userauth': {
            'handlers': ['security', 'console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'voting': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Security and encryption settings (required for vote encryption)
ENCRYPTION_KEY = config('ENCRYPTION_KEY', default='u9EqgHL9a6XlINYv8kGy1lA-NUIeXU7_SE8whm5YmuY=')
# Skip strict check during collectstatic (build phase often has no env vars)
_running_collectstatic = len(__import__('sys').argv) > 1 and 'collectstatic' in __import__('sys').argv[1]
if not DEBUG and not _running_collectstatic:
    from django.core.exceptions import ImproperlyConfigured
    if not ENCRYPTION_KEY or ENCRYPTION_KEY.strip() == '' or ENCRYPTION_KEY == 'u9EqgHL9a6XlINYv8kGy1lA-NUIeXU7_SE8whm5YmuY=':
        raise ImproperlyConfigured(
            'ENCRYPTION_KEY must be set in production (votes are encrypted). '
            'Generate one: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        )
    try:
        from cryptography.fernet import Fernet
        Fernet(ENCRYPTION_KEY.encode())
    except Exception:
        raise ImproperlyConfigured(
            'ENCRYPTION_KEY must be a valid Fernet key. '
            'Generate one: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        )
VOTE_ENCRYPTION_ALGORITHM = 'AES-256-GCM'
AUDIT_LOG_RETENTION_DAYS = 2555  # 7 years

# Election settings
MAX_VOTERS_PER_ELECTION = 100000000
VOTE_ANONYMIZATION_SALT = config('VOTE_ANONYMIZATION_SALT', default='default-salt-change-in-production')
BLOCKCHAIN_ENABLED = config('BLOCKCHAIN_ENABLED', default=False, cast=bool)

# Notification settings
NOTIFICATION_ENABLED = True
SMS_PROVIDER = config('SMS_PROVIDER', default='twilio')
SMS_API_KEY = config('SMS_API_KEY', default='')
EMAIL_FROM_ADDRESS = config('EMAIL_FROM_ADDRESS', default='noreply@voting-system.com')
DEFAULT_FROM_EMAIL = EMAIL_FROM_ADDRESS

# hCaptcha (vote submission)
HCAPTCHA_SITE_KEY = config('HCAPTCHA_SITE_KEY', default='')
HCAPTCHA_SECRET_KEY = config('HCAPTCHA_SECRET_KEY', default='')
HCAPTCHA_ENABLED = config('HCAPTCHA_ENABLED', default=False, cast=bool)

# Google reCAPTCHA v2 (vote submission)
RECAPTCHA_SITE_KEY = config('RECAPTCHA_SITE_KEY', default='')
RECAPTCHA_SECRET_KEY = config('RECAPTCHA_SECRET_KEY', default='')
RECAPTCHA_ENABLED = config('RECAPTCHA_ENABLED', default=True, cast=bool)

# Django-recaptcha compatibility
RECAPTCHA_PUBLIC_KEY = RECAPTCHA_SITE_KEY
RECAPTCHA_PRIVATE_KEY = RECAPTCHA_SECRET_KEY

# reCAPTCHA Enterprise (optional upgrade for vote submission; takes precedence when enabled)
RECAPTCHA_ENTERPRISE_ENABLED = config('RECAPTCHA_ENTERPRISE_ENABLED', default=False, cast=bool)
RECAPTCHA_ENTERPRISE_PROJECT_ID = config('RECAPTCHA_ENTERPRISE_PROJECT_ID', default='')
RECAPTCHA_ENTERPRISE_SITE_KEY = config('RECAPTCHA_ENTERPRISE_SITE_KEY', default='')
RECAPTCHA_ENTERPRISE_API_KEY = config('RECAPTCHA_ENTERPRISE_API_KEY', default='')

# Twilio (phone OTP)
TWILIO_ACCOUNT_SID = config('TWILIO_ACCOUNT_SID', default='')
TWILIO_AUTH_TOKEN = config('TWILIO_AUTH_TOKEN', default='')
TWILIO_PHONE_NUMBER = config('TWILIO_PHONE_NUMBER', default='')
# Send OTP SMS synchronously by default so phone verification works without a Celery worker.
# Set to False to queue via Celery.
PHONE_OTP_SYNC_SEND = config('PHONE_OTP_SYNC_SEND', default=True, cast=bool)

# Performance settings
ENABLE_QUERY_CACHING = True
DATABASE_POOL_SIZE = 20
DATABASE_MAX_OVERFLOW = 30

# Compliance settings
GDPR_COMPLIANCE = True
DATA_RETENTION_DAYS = 2555
AUDIT_LOG_IMMUTABLE = True

# Redirect URLs
LOGIN_REDIRECT_URL = '/'
ACCOUNT_LOGOUT_REDIRECT_URL = '/'

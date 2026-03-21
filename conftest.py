# Ensure Django is configured before pytest collects/imports test modules
# (avoids ImproperlyConfigured when tests.py imports voting.models)
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'engine.settings')

import django
django.setup()

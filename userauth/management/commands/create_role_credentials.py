"""
Create one user per application role for local/dev and demo use.

Usage:
  python manage.py create_role_credentials
  python manage.py create_role_credentials --password mysecret
  DEV_PASSWORD=mysecret python manage.py create_role_credentials

Creates users with emails like voter@example.com, super_admin@example.com, etc.
See docs/AUTH_CREDENTIALS.md for the full list and default password.
"""
import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

# (role, email, is_staff, is_superuser, is_verified)
ROLE_CREDENTIALS = [
    ('super_admin', 'super_admin@example.com', True, True, True),
    ('election_admin', 'election_admin@example.com', False, False, True),
    ('org_admin', 'org_admin@example.com', False, False, True),
    ('voter', 'voter@example.com', False, False, True),
    ('auditor', 'auditor@example.com', False, False, True),
    ('monitor', 'monitor@example.com', False, False, True),
]


class Command(BaseCommand):
    help = 'Create one user per role (super_admin, election_admin, org_admin, voter, auditor, monitor) for dev/demo.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--password',
            type=str,
            default=os.environ.get('DEV_PASSWORD', 'devpass123'),
            help='Password for all created users (default: DEV_PASSWORD env or "devpass123").',
        )
        parser.add_argument(
            '--no-input',
            action='store_true',
            help='Do not prompt; use default or env password.',
        )

    def handle(self, *args, **options):
        User = get_user_model()
        password = options['password'] or os.environ.get('DEV_PASSWORD', 'devpass123')
        if not options['no_input'] and password == 'devpass123':
            self.stdout.write(self.style.WARNING('Using default password "devpass123". Set DEV_PASSWORD or --password for production-like envs.'))
        created = 0
        updated = 0
        for role, email, is_staff, is_superuser, is_verified in ROLE_CREDENTIALS:
            user, was_created = User.objects.update_or_create(
                email__iexact=email,
                defaults={
                    'email': email,
                    'role': role,
                    'is_staff': is_staff,
                    'is_superuser': is_superuser,
                    'is_verified': is_verified,
                    'is_active': True,
                    'citizenship_country': 'US',
                    'first_name': role.replace('_', ' ').title(),
                    'last_name': '(Dev)',
                },
            )
            user.set_password(password)
            if was_created:
                user.save(update_fields=['password'])
                created += 1
                self.stdout.write(self.style.SUCCESS(f'Created: {email} (role={role})'))
            else:
                user.email = email
                user.role = role
                user.is_staff = is_staff
                user.is_superuser = is_superuser
                user.is_verified = is_verified
                user.citizenship_country = user.citizenship_country or 'US'
                user.save(update_fields=['password', 'email', 'role', 'is_staff', 'is_superuser', 'is_verified', 'citizenship_country'])
                updated += 1
                self.stdout.write(f'Updated: {email} (role={role})')
        self.stdout.write(self.style.SUCCESS(f'Done. Created {created}, updated {updated}. See docs/AUTH_CREDENTIALS.md for login details.'))

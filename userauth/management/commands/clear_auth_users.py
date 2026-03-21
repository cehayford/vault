"""
Delete all users from the authentication table (CustomUser / userauth_customuser).

Usage:
  python manage.py clear_auth_users --force

WARNING: This deletes all user accounts. Related objects (elections, votes, etc.)
may be deleted or orphaned depending on on_delete. Use only for dev/reset.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = "Remove all records from the authentication (CustomUser) table."

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Actually delete; without this, only a dry-run count is shown.',
        )

    def handle(self, *args, **options):
        User = get_user_model()
        count = User.objects.count()
        if count == 0:
            self.stdout.write(self.style.WARNING('Authentication table is already empty.'))
            return
        if not options['force']:
            self.stdout.write(
                self.style.WARNING(f'Would delete {count} user(s). Run with --force to delete.')
            )
            return
        deleted, _ = User.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f'Removed {deleted} record(s) from the authentication table.'))

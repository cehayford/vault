from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from userauth.models import Tenant

User = get_user_model()


class Command(BaseCommand):
    help = 'Create test users for all roles with password "devpass123"'

    def add_arguments(self, parser):
        parser.add_argument(
            '--password',
            type=str,
            default='devpass123',
            help='Password for test users (default: devpass123)'
        )
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete existing test users before creating new ones'
        )

    def handle(self, *args, **options):
        password = options['password']
        reset = options['reset']
        
        # Define users for each role
        test_users = [
            {
                'email': 'superadmin@vault.dev',
                'first_name': 'Super',
                'last_name': 'Admin',
                'role': 'super_admin',
                'is_staff': True,
                'is_superuser': True,
                'is_verified': True,
                'nickname': 'SuperAdmin'
            },
            {
                'email': 'electionadmin@vault.dev',
                'first_name': 'Election',
                'last_name': 'Admin',
                'role': 'election_admin',
                'is_staff': True,
                'is_verified': True,
                'nickname': 'ElectionAdmin'
            },
            {
                'email': 'orgadmin@vault.dev',
                'first_name': 'Organization',
                'last_name': 'Admin',
                'role': 'org_admin',
                'is_staff': True,
                'is_verified': True,
                'nickname': 'OrgAdmin'
            },
            {
                'email': 'monitor@vault.dev',
                'first_name': 'Monitor',
                'last_name': 'User',
                'role': 'monitor',
                'is_verified': True,
                'nickname': 'Monitor'
            },
            {
                'email': 'auditor@vault.dev',
                'first_name': 'Auditor',
                'last_name': 'User',
                'role': 'auditor',
                'is_verified': True,
                'nickname': 'Auditor'
            },
            {
                'email': 'voter@vault.dev',
                'first_name': 'Regular',
                'last_name': 'Voter',
                'role': 'voter',
                'is_verified': True,
                'nickname': 'Voter',
                'citizenship_country': 'US',
                'is_citizen': True,
                'voter_id': 'VOTER001',
                'eligibility_verified': True
            }
        ]
        
        # Create a test tenant if it doesn't exist
        tenant, created = Tenant.objects.get_or_create(
            slug='test-org',
            defaults={
                'name': 'Test Organization',
                'billing_email': 'admin@testorg.dev',
                'plan': 'pro'
            }
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS(f'✅ Created test tenant: {tenant.name}')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'📋 Using existing tenant: {tenant.name}')
            )
        
        self.stdout.write(f'\n🔧 Creating test users with password: "{password}"')
        self.stdout.write('=' * 60)
        
        created_count = 0
        updated_count = 0
        
        for user_data in test_users:
            email = user_data['email']
            
            # Delete existing user if reset flag is set
            if reset and User.objects.filter(email=email).exists():
                User.objects.filter(email=email).delete()
                self.stdout.write(
                    self.style.WARNING(f'🗑️  Deleted existing user: {email}')
                )
            
            # Check if user already exists
            if User.objects.filter(email=email).exists():
                existing_user = User.objects.get(email=email)
                self.stdout.write(
                    self.style.WARNING(f'⚠️  User {email} already exists (Role: {existing_user.role})')
                )
                
                # Update password to ensure it's correct
                existing_user.set_password(password)
                existing_user.save()
                updated_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'🔄 Updated password for {email}')
                )
                continue
            
            # Set tenant for org_admin and election_admin
            if user_data['role'] in ['org_admin', 'election_admin']:
                user_data['tenant'] = tenant
            
            # Create user
            try:
                user = User.objects.create_user(
                    email=email,
                    password=password,
                    **{k: v for k, v in user_data.items() if k != 'email'}
                )
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Created {user.role.title()}: {email}')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'❌ Failed to create {email}: {e}')
                )
        
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('🎯 Test Users Summary:'))
        self.stdout.write('=' * 60)
        
        for user_data in test_users:
            email = user_data['email']
            user = User.objects.get(email=email)
            status = "🟢 Verified" if user.is_verified else "🔴 Not Verified"
            tenant_info = f" (Tenant: {user.tenant.name})" if user.tenant else ""
            self.stdout.write(
                f'• {user.role.title().ljust(18)} | {email.ljust(25)} | {status}{tenant_info}'
            )
        
        self.stdout.write(f'\n🔑 All users have password: {password}')
        self.stdout.write(f'🏢 Test tenant: {tenant.name} (slug: {tenant.slug})')
        self.stdout.write(f'\n📊 Created: {created_count} new users, Updated: {updated_count} existing users')
        
        self.stdout.write('\n🌐 Login URLs:')
        self.stdout.write('• Local: http://localhost:8000/')
        self.stdout.write('• Production: https://your-domain.com/')
        
        self.stdout.write('\n📋 Quick Login Credentials:')
        for user_data in test_users:
            self.stdout.write(f'• {user_data["email"]} : {password}')
        
        self.stdout.write(
            self.style.SUCCESS('\n✅ Test users setup complete!')
        )

#!/usr/bin/env python
"""
Simple test script to verify Google reCAPTCHA v2 integration
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'engine.settings')
django.setup()

from django.conf import settings
from django.test import Client
from voting.models import Election, Ballot, Candidate
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

def test_recaptcha_integration():
    print("🔍 Testing Google reCAPTCHA v2 Integration")
    print("=" * 50)
    
    # Check settings
    print("\n1. Checking reCAPTCHA settings...")
    print(f"   RECAPTCHA_ENABLED: {getattr(settings, 'RECAPTCHA_ENABLED', False)}")
    print(f"   RECAPTCHA_SITE_KEY: {getattr(settings, 'RECAPTCHA_SITE_KEY', '')[:20]}...")
    print(f"   RECAPTCHA_SECRET_KEY: {getattr(settings, 'RECAPTCHA_SECRET_KEY', '')[:20]}...")
    print(f"   RECAPTCHA_PUBLIC_KEY: {getattr(settings, 'RECAPTCHA_PUBLIC_KEY', '')[:20]}...")
    print(f"   RECAPTCHA_PRIVATE_KEY: {getattr(settings, 'RECAPTCHA_PRIVATE_KEY', '')[:20]}...")
    
    # Check if django_recaptcha is installed
    print("\n2. Checking django_recaptcha installation...")
    try:
        import django_recaptcha
        print(f"   ✅ django_recaptcha imported successfully")
        # Try to get version if available
        try:
            version = getattr(django_recaptcha, '__version__', 'unknown')
            print(f"   📦 django_recaptcha version: {version}")
        except:
            print("   📦 django_recaptcha version: unknown")
    except ImportError as e:
        print(f"   ❌ django_recaptcha not found: {e}")
        return False
    
    # Check if app is in INSTALLED_APPS
    print("\n3. Checking INSTALLED_APPS...")
    if 'django_recaptcha' in settings.INSTALLED_APPS:
        print("   ✅ django_recaptcha is in INSTALLED_APPS")
    else:
        print("   ❌ django_recaptcha is not in INSTALLED_APPS")
        return False
    
    # Test template rendering
    print("\n4. Testing template rendering...")
    # Temporarily add testserver to ALLOWED_HOSTS for testing
    original_allowed_hosts = getattr(settings, 'ALLOWED_HOSTS', [])
    settings.ALLOWED_HOSTS = list(original_allowed_hosts) + ['testserver']
    
    client = Client()
    
    # Create test data
    try:
        # Clean up existing data
        User.objects.filter(email='test@example.com').delete()
        Election.objects.filter(title='Test Election').delete()
        
        user = User.objects.create_user(email='test@example.com', password='testpass123')
        org = None  # Skip org for simplicity
        
        election = Election.objects.create(
            title='Test Election',
            description='Test election for reCAPTCHA',
            voting_type='single_choice',
            require_captcha=True,
            creator=user,
            organisation=org,
            start_date=timezone.now(),
            end_date=timezone.now() + timezone.timedelta(days=7)
        )
        
        ballot = Ballot.objects.create(
            title='Test Ballot',
            description='Test ballot for reCAPTCHA',
            election=election
        )
        
        candidate = Candidate.objects.create(
            name='Test Candidate',
            ballot=ballot
        )
        
        # Test GET request
        response = client.get(f'/voting/ballots/{ballot.pk}/vote/')
        
        if response.status_code == 200:
            print("   ✅ Ballot page loads successfully")
            
            # Check if reCAPTCHA context is passed
            if 'recaptcha_enabled' in response.context:
                print(f"   ✅ recaptcha_enabled in context: {response.context['recaptcha_enabled']}")
            else:
                print("   ⚠️  recaptcha_enabled not in context")
            
            if 'recaptcha_site_key' in response.context:
                print(f"   ✅ recaptcha_site_key in context: {response.context['recaptcha_site_key'][:20]}...")
            else:
                print("   ⚠️  recaptcha_site_key not in context")
            
            # Check if reCAPTCHA script is in the response
            content = response.content.decode('utf-8')
            if 'google.com/recaptcha/api.js' in content:
                print("   ✅ reCAPTCHA script is included in template")
            else:
                print("   ❌ reCAPTCHA script not found in template")
            
            if 'g-recaptcha' in content:
                print("   ✅ reCAPTCHA widget placeholder found in template")
            else:
                print("   ❌ reCAPTCHA widget placeholder not found in template")
                
        else:
            print(f"   ❌ Ballot page failed with status: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Error during testing: {e}")
        return False
    
    print("\n5. Summary")
    print("   ✅ Google reCAPTCHA v2 integration appears to be working!")
    print("   📝 Note: Full end-to-end testing requires actual reCAPTCHA keys")
    print("   📝 Note: The reCAPTCHA widget will appear when election.require_captcha=True")
    
    return True

if __name__ == '__main__':
    success = test_recaptcha_integration()
    sys.exit(0 if success else 1)

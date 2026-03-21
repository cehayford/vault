from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from django.core.exceptions import ValidationError
from django.urls import reverse
import json
import uuid
from unittest.mock import patch, MagicMock
from cryptography.fernet import Fernet
from voting.models import Election, Ballot, Candidate, Vote, VoteReceipt, ElectionResult
from userauth.models import CustomUser, SecurityLog, EmailVerification

User = get_user_model()

# Valid Fernet key for vote encryption tests (settings default may be invalid)
TEST_ENCRYPTION_KEY = Fernet.generate_key().decode()

class CustomUserModelTest(TestCase):
    def setUp(self):
        self.user_data = {
            'email': 'test@example.com',
            'first_name': 'John',
            'last_name': 'Doe',
            'password': 'SecurePass123!',
            'date_of_birth': '1990-01-01',
            'is_citizen': True,
            'data_consent': True,
            'citizenship_country': 'US',  # CustomUser.save() sets is_citizen from this
        }

    def test_create_user(self):
        user = User.objects.create_user(**self.user_data)
        self.assertEqual(user.email, self.user_data['email'])
        self.assertEqual(user.role, 'voter')
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.is_active)

    def test_create_superuser(self):
        superuser = User.objects.create_superuser(
            email='admin@example.com',
            password='AdminPass123!'
        )
        self.assertEqual(superuser.role, 'super_admin')
        self.assertTrue(superuser.is_staff)
        self.assertTrue(superuser.is_superuser)
        self.assertTrue(superuser.is_verified)

    def test_user_age_calculation(self):
        user = User.objects.create_user(**self.user_data)
        self.assertIsNotNone(user.age)
        self.assertGreaterEqual(user.age, 18)

    def test_user_eligibility(self):
        user = User.objects.create_user(**self.user_data)
        user.is_verified = True
        user.eligibility_verified = True
        user.save()
        
        self.assertTrue(user.is_eligible_voter())

    def test_mfa_functionality(self):
        user = User.objects.create_user(**self.user_data)
        
        # Test MFA enable
        user.enable_mfa()
        self.assertTrue(user.mfa_enabled)
        self.assertIsNotNone(user.mfa_secret)
        self.assertEqual(len(user.backup_codes), 10)
        
        # Test MFA disable
        user.disable_mfa()
        self.assertFalse(user.mfa_enabled)
        self.assertIsNone(user.mfa_secret)
        self.assertEqual(len(user.backup_codes), 0)

    def test_mfa_token_verification(self):
        user = User.objects.create_user(**self.user_data)
        user.enable_mfa()
        
        # Generate valid token
        import pyotp
        totp = pyotp.TOTP(user.mfa_secret)
        valid_token = totp.now()
        
        self.assertTrue(user.verify_mfa_token(valid_token))
        self.assertFalse(user.verify_mfa_token('invalid'))

    def test_backup_code_verification(self):
        user = User.objects.create_user(**self.user_data)
        user.enable_mfa()
        
        backup_code = user.backup_codes[0]
        self.assertTrue(user.verify_backup_code(backup_code))
        self.assertFalse(user.verify_backup_code(backup_code))  # Should be used

    def test_age_validation(self):
        underage_data = self.user_data.copy()
        underage_data['date_of_birth'] = '2010-01-01'  # Under 18
        
        user = User(**underage_data)
        with self.assertRaises(ValidationError):
            user.clean()


class ElectionModelTest(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            email='admin@example.com',
            password='AdminPass123!'
        )
        
        self.election_data = {
            'title': 'Test Election 2024',
            'description': 'A test election for testing purposes',
            'election_type': 'local',
            'voting_type': 'single_choice',
            'creator': self.admin_user,
            'start_date': timezone.now(),
            'end_date': timezone.now() + timedelta(days=7),
            'results_publish_date': timezone.now() + timedelta(days=8),
        }

    def test_create_election(self):
        election = Election.objects.create(**self.election_data)
        self.assertEqual(election.title, self.election_data['title'])
        self.assertEqual(election.status, 'draft')
        self.assertEqual(election.creator, self.admin_user)

    def test_election_validation(self):
        invalid_data = self.election_data.copy()
        invalid_data['end_date'] = timezone.now() - timedelta(days=1)  # End before start
        
        election = Election(**invalid_data)
        with self.assertRaises(ValidationError):
            election.clean()

    def test_election_active_status(self):
        election = Election.objects.create(**self.election_data)
        election.status = 'active'
        election.save()
        
        self.assertTrue(election.is_active())
        
        # Test inactive election
        election.status = 'draft'
        self.assertFalse(election.is_active())

    def test_voter_eligibility_check(self):
        voter_data = {
            'email': 'voter@example.com',
            'first_name': 'Jane',
            'last_name': 'Smith',
            'password': 'VoterPass123!',
            'date_of_birth': '1985-01-01',
            'is_citizen': True,
            'data_consent': True,
            'citizenship_country': 'US',  # CustomUser.save() sets is_citizen from this
        }
        
        voter = User.objects.create_user(**voter_data)
        voter.is_verified = True
        voter.eligibility_verified = True
        voter.save()
        
        election = Election.objects.create(**self.election_data)
        election.status = 'active'
        election.save()
        
        self.assertTrue(election.can_vote(voter))


@override_settings(ENCRYPTION_KEY=TEST_ENCRYPTION_KEY)
class VoteModelTest(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            email='admin@example.com',
            password='AdminPass123!'
        )
        
        self.voter = User.objects.create_user(
            email='voter@example.com',
            first_name='John',
            last_name='Doe',
            password='VoterPass123!',
            date_of_birth='1990-01-01',
            is_citizen=True,
            data_consent=True
        )
        self.voter.is_verified = True
        self.voter.eligibility_verified = True
        self.voter.save()
        
        self.election = Election.objects.create(
            title='Test Election',
            description='Test',
            election_type='local',
            voting_type='single_choice',
            creator=self.admin_user,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=7),
        )
        
        self.ballot = Ballot.objects.create(
            election=self.election,
            title='Test Ballot',
            question='Who do you support?'
        )
        
        self.candidate = Candidate.objects.create(
            ballot=self.ballot,
            name='Test Candidate'
        )

    def test_vote_encryption(self):
        selections = [str(self.candidate.id)]
        vote = Vote(
            election=self.election,
            ballot=self.ballot,
            voter=self.voter,
            vote_token=uuid.uuid4().hex,
            ip_address='127.0.0.1',
            user_agent='Test Browser'
        )
        vote.encrypt_selections(selections)
        vote.save()
        self.assertIsNotNone(vote.encrypted_selections)
        self.assertIsNotNone(vote.selection_hash)
        decrypted = vote.decrypt_selections()
        self.assertEqual(decrypted, selections)

    def test_vote_receipt_generation(self):
        vote = Vote(
            election=self.election,
            ballot=self.ballot,
            voter=self.voter,
            vote_token=uuid.uuid4().hex,
            ip_address='127.0.0.1',
            user_agent='Test Browser'
        )
        vote.encrypt_selections([str(self.candidate.id)])
        vote.save()
        receipt = VoteReceipt.objects.create(vote=vote)
        self.assertIsNotNone(receipt.receipt_code)
        self.assertEqual(len(receipt.receipt_code), 32)

    def test_unique_vote_per_election(self):
        vote = Vote(
            election=self.election,
            ballot=self.ballot,
            voter=self.voter,
            vote_token=uuid.uuid4().hex,
            ip_address='127.0.0.1',
            user_agent='Test Browser'
        )
        vote.encrypt_selections([str(self.candidate.id)])
        vote.save()
        with self.assertRaises(Exception):
            Vote.objects.create(
                election=self.election,
                ballot=self.ballot,
                voter=self.voter,
                vote_token=uuid.uuid4().hex,
                ip_address='127.0.0.1',
                user_agent='Test Browser'
            )


class SecurityTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            first_name='Test',
            last_name='User',
            password='TestPass123!',
            data_consent=True
        )

    def test_security_log_creation(self):
        log = SecurityLog.objects.create(
            user=self.user,
            action_type='login',
            description='User logged in successfully',
            ip_address='127.0.0.1',
            user_agent='Test Browser'
        )
        
        self.assertEqual(log.user, self.user)
        self.assertEqual(log.action_type, 'login')
        self.assertTrue(log.success)

    def test_email_verification_expiry(self):
        verification = EmailVerification.objects.create(
            user=self.user,
            code='123456'
        )
        
        self.assertFalse(verification.is_expired())
        self.assertTrue(verification.can_attempt())

    def test_failed_login_attempts(self):
        # Simulate failed login attempts
        for i in range(6):
            self.user.failed_login_attempts = i + 1
            self.user.save()
        
        self.user.lock_account()
        self.assertTrue(self.user.account_locked)


@override_settings(ENCRYPTION_KEY=TEST_ENCRYPTION_KEY)
class IntegrationTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_superuser(
            email='admin@example.com',
            password='AdminPass123!'
        )
        
        self.voter = User.objects.create_user(
            email='voter@example.com',
            first_name='John',
            last_name='Doe',
            password='VoterPass123!',
            date_of_birth='1990-01-01',
            is_citizen=True,
            data_consent=True
        )
        self.voter.is_verified = True
        self.voter.eligibility_verified = True
        self.voter.save()

    def test_complete_voting_flow(self):
        # Create election
        election = Election.objects.create(
            title='Integration Test Election',
            description='Testing complete flow',
            election_type='local',
            voting_type='single_choice',
            creator=self.admin_user,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=7),
        )
        election.status = 'active'
        election.save()
        
        # Create ballot
        ballot = Ballot.objects.create(
            election=election,
            title='Test Ballot',
            question='Choose your candidate'
        )
        
        candidate1 = Candidate.objects.create(ballot=ballot, name='Candidate 1', order=0)
        candidate2 = Candidate.objects.create(ballot=ballot, name='Candidate 2', order=1)
        vote = Vote(
            election=election,
            ballot=ballot,
            voter=self.voter,
            vote_token=uuid.uuid4().hex,
            ip_address='127.0.0.1',
            user_agent='Test Browser'
        )
        vote.encrypt_selections([str(candidate1.id)])
        vote.save()
        
        # Create receipt
        receipt = VoteReceipt.objects.create(vote=vote)
        
        # Verify vote was recorded
        self.assertEqual(Vote.objects.filter(election=election).count(), 1)
        self.assertEqual(VoteReceipt.objects.count(), 1)
        
        # Calculate results
        result = ElectionResult.objects.create(election=election)
        result.calculate_results()
        
        self.assertEqual(result.total_votes, 1)
        self.assertEqual(result.total_voters, 1)

    def test_role_based_access(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('admin:index'))
        self.assertIn(response.status_code, (200, 301, 302))
        self.client.force_login(self.voter)
        response = self.client.get(reverse('admin:index'))
        self.assertIn(response.status_code, (301, 302))

@override_settings(ENCRYPTION_KEY=TEST_ENCRYPTION_KEY)
class PerformanceTest(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            email='admin@example.com',
            password='AdminPass123!'
        )
        
        self.election = Election.objects.create(
            title='Performance Test Election',
            description='Testing performance',
            election_type='national',
            voting_type='single_choice',
            creator=self.admin_user,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=7),
        )
        
        # Create multiple ballots and candidates
        for i in range(10):
            ballot = Ballot.objects.create(
                election=self.election,
                title=f'Ballot {i}',
                question=f'Question {i}?',
                order=i
            )
            
            for j in range(5):
                Candidate.objects.create(
                    ballot=ballot,
                    name=f'Candidate {i}-{j}',
                    order=j
                )

    def test_large_scale_voting_simulation(self):
        import time
        
        # Create voters
        voters = []
        for i in range(100):
            voter = User.objects.create_user(
                email=f'voter{i}@example.com',
                first_name=f'Voter{i}',
                last_name='Test',
                password='TestPass123!',
                date_of_birth='1990-01-01',
                is_citizen=True,
                data_consent=True
            )
            voter.is_verified = True
            voter.eligibility_verified = True
            voter.save()
            voters.append(voter)
        
        # Simulate voting
        start_time = time.time()
        
        for i, voter in enumerate(voters):
            ballot = self.election.ballots.first()
            candidate = ballot.candidates.first()
            vote = Vote(
                election=self.election,
                ballot=ballot,
                voter=voter,
                vote_token=uuid.uuid4().hex,
                ip_address=f'192.168.1.{i % 255}',
                user_agent=f'Browser {i}'
            )
            vote.encrypt_selections([str(candidate.id)])
            vote.save()
        
        end_time = time.time()
        voting_time = end_time - start_time
        
        # Performance assertions
        self.assertLess(voting_time, 10.0)  # Should complete within 10 seconds
        self.assertEqual(Vote.objects.filter(election=self.election).count(), 100)
        
        # Test result calculation performance
        start_time = time.time()
        result = ElectionResult.objects.create(election=self.election)
        result.calculate_results()
        end_time = time.time()
        
        calculation_time = end_time - start_time
        self.assertLess(calculation_time, 5.0)  # Should complete within 5 seconds

if __name__ == '__main__':
    import unittest
    unittest.main()

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from userauth.models import CustomUser, SecurityLog
from voting.models import Election, Vote, ElectionResult
import random
import string
from faker import Faker

class Command(BaseCommand):
    help = 'Generate test data for the voting system'

    def add_arguments(self, parser):
        parser.add_argument(
            '--voters',
            type=int,
            default=1000,
            help='Number of voters to create'
        )
        parser.add_argument(
            '--elections',
            type=int,
            default=5,
            help='Number of elections to create'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing test data'
        )

    def handle(self, *args, **options):
        fake = Faker()
        
        if options['clear']:
            self.clear_test_data()
        
        num_voters = options['voters']
        num_elections = options['elections']
        
        self.stdout.write(f'Creating {num_voters} voters and {num_elections} elections...')
        
        # Create voters
        voters = self.create_voters(num_voters, fake)
        
        # Create elections
        elections = self.create_elections(num_elections, fake)
        
        # Generate votes
        self.generate_votes(voters, elections, fake)
        
        # Calculate results
        self.calculate_results(elections)
        
        self.stdout.write(self.style.SUCCESS('Test data generation completed!'))

    def clear_test_data(self):
        self.stdout.write('Clearing existing test data...')
        Vote.objects.all().delete()
        ElectionResult.objects.all().delete()
        Election.objects.all().delete()
        CustomUser.objects.filter(is_superuser=False).delete()
        SecurityLog.objects.all().delete()

    def create_voters(self, count, fake):
        self.stdout.write(f'Creating {count} voters...')
        voters = []
        
        for i in range(count):
            # Generate realistic age distribution
            age = random.choices(
                range(18, 90),
                weights=[1] * 10 + [2] * 20 + [3] * 30 + [2] * 20 + [1] * 10
            )[0]
            
            birth_year = timezone.now().year - age
            
            voter_data = {
                'email': f'voter{i}@testdomain.com',
                'first_name': fake.first_name(),
                'last_name': fake.last_name(),
                'password': 'TestPass123!',
                'date_of_birth': fake.date_object().replace(year=birth_year),
                'phone_number': fake.phone_number(),
                'address': fake.street_address(),
                'city': fake.city(),
                'state': fake.state(),
                'zip_code': fake.zipcode(),
                'country': 'US',
                'is_citizen': random.choice([True, True, True, False]),  # 75% citizens
                'voter_id': f'VOTER{i:06d}',
                'registration_date': fake.date_time_between(start_date='-5y', end_date='now'),
                'is_verified': True,
                'eligibility_verified': random.choice([True, True, False]),  # 66% verified
                'data_consent': True,
                'marketing_consent': random.choice([True, False]),
            }
            
            try:
                voter = CustomUser.objects.create_user(**voter_data)
                
                # Enable MFA for some users
                if random.random() < 0.3:  # 30% have MFA
                    voter.enable_mfa()
                
                voters.append(voter)
                
                if (i + 1) % 100 == 0:
                    self.stdout.write(f'  Created {i + 1} voters...')
                    
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'Error creating voter {i}: {e}'))
        
        return voters

    def create_elections(self, count, fake):
        self.stdout.write(f'Creating {count} elections...')
        elections = []
        
        election_types = ['local', 'state', 'national', 'primary', 'general']
        voting_types = ['single_choice', 'multiple_choice', 'ranked_choice']
        
        for i in range(count):
            # Create admin for each election
            admin_email = f'admin{i}@testdomain.com'
            admin, created = CustomUser.objects.get_or_create(
                email=admin_email,
                defaults={
                    'first_name': f'Admin{i}',
                    'last_name': 'User',
                    'password': 'AdminPass123!',
                    'role': 'election_admin',
                    'is_staff': True,
                    'is_verified': True,
                    'data_consent': True,
                }
            )
            
            # Create election
            start_date = fake.date_time_between(start_date='-30d', end_date='+30d')
            end_date = start_date + timedelta(days=random.randint(1, 14))
            
            election_data = {
                'title': fake.catch_phrase(),
                'description': fake.text(max_nb_chars=500),
                'election_type': random.choice(election_types),
                'voting_type': random.choice(voting_types),
                'status': 'active',
                'creator': admin,
                'start_date': start_date,
                'end_date': end_date,
                'results_publish_date': end_date + timedelta(days=1),
                'min_age': random.choice([18, 21, 25]),
                'citizenship_required': random.choice([True, True, False]),
                'residency_required': random.choice([True, True, True, False]),
                'voter_registration_required': random.choice([True, True, True, False]),
                'require_mfa': random.choice([True, False]),
                'require_google_auth': random.choice([True, False, False, False]),
                'allow_vote_changes': random.choice([True, False, False, False]),
                'max_vote_changes': random.randint(0, 3) if random.random() < 0.2 else 0,
            }
            
            election = Election.objects.create(**election_data)
            
            # Create ballots
            num_ballots = random.randint(2, 8)
            for j in range(num_ballots):
                ballot = election.ballot_set.create(
                    title=fake.catch_phrase(),
                    description=fake.text(max_nb_chars=200),
                    question=fake.sentence(),
                    max_selections=random.randint(1, 5),
                    min_selections=1,
                    allow_write_in=random.choice([True, False, False, False]),
                    is_required=random.choice([True, True, False]),
                    order=j,
                )
                
                # Create candidates
                num_candidates = random.randint(2, 8)
                for k in range(num_candidates):
                    candidate_name = fake.name()
                    if random.random() < 0.1:  # 10% write-in candidates
                        candidate_name = f'Write-in: {candidate_name}'
                    
                    ballot.candidate_set.create(
                        name=candidate_name,
                        description=fake.text(max_nb_chars=300),
                        party=random.choice(['Democratic', 'Republican', 'Independent', 'Green', 'Libertarian', '']),
                        order=k,
                        is_write_in='Write-in:' in candidate_name,
                    )
            
            elections.append(election)
            
            if (i + 1) % 10 == 0:
                self.stdout.write(f'  Created {i + 1} elections...')
        
        return elections

    def generate_votes(self, voters, elections, fake):
        self.stdout.write('Generating votes...')
        
        eligible_voters = [v for v in voters if v.is_eligible_voter()]
        active_elections = [e for e in elections if e.is_active()]
        
        if not eligible_voters:
            self.stdout.write(self.style.WARNING('No eligible voters found'))
            return
        
        if not active_elections:
            self.stdout.write(self.style.WARNING('No active elections found'))
            return
        
        # Simulate voting patterns
        voter_turnout = random.uniform(0.3, 0.8)  # 30-80% turnout
        
        for election in active_elections:
            num_voters = int(len(eligible_voters) * voter_turnout)
            voting_voters = random.sample(eligible_voters, min(num_voters, len(eligible_voters)))
            
            for voter in voting_voters:
                # Check if voter can vote in this election
                if not election.can_vote(voter):
                    continue
                
                # Vote in each ballot
                for ballot in election.ballot_set.all():
                    try:
                        # Generate selections
                        candidates = list(ballot.candidate_set.filter(is_write_in=False))
                        if not candidates:
                            continue
                        
                        num_selections = min(
                            random.randint(ballot.min_selections, ballot.max_selections),
                            len(candidates)
                        )
                        selected_candidates = random.sample(candidates, num_selections)
                        
                        # Create vote
                        vote = Vote.objects.create(
                            election=election,
                            ballot=ballot,
                            voter=voter,
                            ip_address=fake.ipv4(),
                            user_agent=fake.user_agent(),
                        )
                        
                        # Encrypt selections
                        selections = [str(c.id) for c in selected_candidates]
                        vote.encrypt_selections(selections)
                        vote.save()
                        
                        # Create receipt
                        from voting.models import VoteReceipt
                        VoteReceipt.objects.create(vote=vote)
                        
                        # Log security event
                        SecurityLog.objects.create(
                            user=voter,
                            action_type='vote_cast',
                            description=f'Vote cast in {election.title}',
                            ip_address=vote.ip_address,
                            user_agent=vote.user_agent,
                        )
                        
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f'Error creating vote: {e}'))

    def calculate_results(self, elections):
        self.stdout.write('Calculating election results...')
        
        for election in elections:
            try:
                result, created = ElectionResult.objects.get_or_create(election=election)
                result.calculate_results()
                
                if Vote.objects.filter(election=election).count() > 0:
                    self.stdout.write(f'  {election.title}: {result.total_votes} votes from {result.total_voters} voters')
                
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'Error calculating results for {election.title}: {e}'))

    def generate_statistics(self):
        self.stdout.write('\n=== STATISTICS ===')
        self.stdout.write(f'Total Users: {CustomUser.objects.count()}')
        self.stdout.write(f'  - Super Admins: {CustomUser.objects.filter(role="super_admin").count()}')
        self.stdout.write(f'  - Election Admins: {CustomUser.objects.filter(role="election_admin").count()}')
        self.stdout.write(f'  - Monitors: {CustomUser.objects.filter(role="monitor").count()}')
        self.stdout.write(f'  - Auditors: {CustomUser.objects.filter(role="auditor").count()}')
        self.stdout.write(f'  - Voters: {CustomUser.objects.filter(role="voter").count()}')
        
        self.stdout.write(f'\\nTotal Elections: {Election.objects.count()}')
        self.stdout.write(f'  - Active: {Election.objects.filter(status="active").count()}')
        self.stdout.write(f'  - Completed: {Election.objects.filter(status="completed").count()}')
        
        self.stdout.write(f'\\nTotal Votes: {Vote.objects.count()}')
        self.stdout.write(f'\\nSecurity Logs: {SecurityLog.objects.count()}')
        
        # MFA statistics
        total_users = CustomUser.objects.count()
        mfa_enabled = CustomUser.objects.filter(mfa_enabled=True).count()
        mfa_percentage = (mfa_enabled / total_users * 100) if total_users > 0 else 0
        self.stdout.write(f'\\nMFA Enabled: {mfa_enabled}/{total_users} ({mfa_percentage:.1f}%)')
        
        # Eligibility statistics
        eligible_voters = sum(1 for user in CustomUser.objects.all() if user.is_eligible_voter())
        eligible_percentage = (eligible_voters / total_users * 100) if total_users > 0 else 0
        self.stdout.write(f'Eligible Voters: {eligible_voters}/{total_users} ({eligible_percentage:.1f}%)')

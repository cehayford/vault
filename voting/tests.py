from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from .models import Organisation, OrgMembership, Election, Ballot, Candidate


class OrgAdminCoreTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email='creator@example.com',
            first_name='Org',
            last_name='Owner',
            password='TestPass123!',
        )
        self.user.role = 'election_admin'
        self.user.save()

    def test_create_organisation_elevates_role_and_creates_membership(self):
        self.client.login(email='creator@example.com', password='TestPass123!')
        resp = self.client.post(
            reverse('voting:create_organisation'),
            data={'name': 'Test Org', 'description': 'Desc'},
        )
        self.assertEqual(resp.status_code, 302)
        org = Organisation.objects.get(name='Test Org')
        membership = OrgMembership.objects.get(organisation=org, user=self.user)
        self.user.refresh_from_db()
        self.assertEqual(membership.role, 'org_admin')
        self.assertEqual(self.user.role, 'org_admin')

    def test_org_dashboard_requires_membership(self):
        User = get_user_model()
        other = User.objects.create_user(
            email='other@example.com',
            first_name='Other',
            last_name='User',
            password='TestPass123!',
        )
        org = Organisation.objects.create(
            name='Scoped Org',
            slug='scoped-org',
            owner=self.user,
        )
        OrgMembership.objects.create(
            organisation=org,
            user=self.user,
            role='org_admin',
            invited_by=self.user,
        )
        # Ensure creator has org_admin role so decorator allows access
        self.user.role = 'org_admin'
        self.user.save()
        # Non-member cannot access
        self.client.login(email='other@example.com', password='TestPass123!')
        resp = self.client.get(reverse('voting:org_dashboard', args=[org.slug]))
        self.assertEqual(resp.status_code, 302)
        # Member can access
        self.client.login(email='creator@example.com', password='TestPass123!')
        resp = self.client.get(reverse('voting:org_dashboard', args=[org.slug]))
        self.assertEqual(resp.status_code, 200)

    def test_created_election_attaches_org_for_org_admin(self):
        # Create org and elevate to org_admin
        self.client.login(email='creator@example.com', password='TestPass123!')
        self.client.post(
            reverse('voting:create_organisation'),
            data={'name': 'Org E', 'description': 'Desc'},
        )
        org = Organisation.objects.get(name='Org E')
        # Create election
        start = timezone.now()
        end = start + timezone.timedelta(days=1)
        resp = self.client.post(
            reverse('voting:create_election'),
            data={
                'title': 'Election E',
                'description': 'Desc',
                'start_date': start,
                'end_date': end,
                'voting_type': 'single_choice',
                'status': 'draft',
                'brand_name': '',
                'primary_color': '',
            },
        )
        self.assertEqual(resp.status_code, 302)
        election = Election.objects.get(title='Election E')
        self.assertEqual(election.organisation, org)


class WorkflowTests(TestCase):
    """Election workflow: state machine and DAG-style validation (single source of truth)."""

    def test_status_transitions_keys_match_model_choices(self):
        from .workflow import ELECTION_STATUS_TRANSITIONS
        model_statuses = {choice[0] for choice in Election.STATUS_CHOICES}
        workflow_statuses = set(ELECTION_STATUS_TRANSITIONS.keys())
        self.assertEqual(model_statuses, workflow_statuses, 'workflow.py must define transitions for every Election.STATUS_CHOICES')

    def test_can_transition_election_status(self):
        from .workflow import can_transition_election_status
        self.assertTrue(can_transition_election_status('draft', 'scheduled'))
        self.assertTrue(can_transition_election_status('draft', 'cancelled'))
        self.assertFalse(can_transition_election_status('draft', 'active'))
        self.assertTrue(can_transition_election_status('active', 'closed'))
        self.assertFalse(can_transition_election_status('completed', 'draft'))

    def test_is_definition_sealed(self):
        from .workflow import is_definition_sealed
        self.assertFalse(is_definition_sealed('draft'))
        self.assertTrue(is_definition_sealed('scheduled'))
        self.assertTrue(is_definition_sealed('active'))
        self.assertTrue(is_definition_sealed('closed'))
        self.assertTrue(is_definition_sealed('completed'))


class DefinitionSealedAndValidationTests(TestCase):
    """Definition flow: sealed elections cannot be modified; validation gate requires ballots before schedule/active."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email='admin@example.com',
            first_name='Admin',
            last_name='User',
            password='TestPass123!',
        )
        self.user.role = 'election_admin'
        self.user.is_verified = True
        self.user.save()

    def test_add_ballot_rejected_when_not_draft(self):
        """Adding a ballot is rejected when election status is scheduled (definition sealed)."""
        start = timezone.now()
        end = start + timezone.timedelta(days=1)
        election = Election.objects.create(
            title='Sealed Election',
            description='Desc',
            election_type='general',
            voting_type='single_choice',
            status='scheduled',
            start_date=start,
            end_date=end,
            creator=self.user,
        )
        self.client.login(email='admin@example.com', password='TestPass123!')
        resp = self.client.post(
            reverse('voting:add_ballot', kwargs={'election_id': election.pk}),
            data={'title': 'B', 'description': '', 'question': 'Q?'},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(election.ballots.exists())
        # Follow redirect and confirm we're on election detail (message shown there)
        resp2 = self.client.get(resp.url) if resp.url else self.client.get(resp.get('Location', ''))
        self.assertEqual(resp2.status_code, 200)
        self.assertIn(b'sealed', resp2.content.lower() or b'')

    def test_status_change_to_scheduled_requires_ballots(self):
        """Transition to scheduled is rejected when election has no ballots."""
        start = timezone.now()
        end = start + timezone.timedelta(days=1)
        election = Election.objects.create(
            title='No Ballots',
            description='Desc',
            election_type='general',
            voting_type='single_choice',
            status='draft',
            start_date=start,
            end_date=end,
            creator=self.user,
        )
        self.client.login(email='admin@example.com', password='TestPass123!')
        resp = self.client.post(
            reverse('voting:election_status_change', kwargs={'pk': election.pk}),
            data={'next_status': 'scheduled'},
        )
        self.assertEqual(resp.status_code, 302)
        election.refresh_from_db()
        self.assertEqual(election.status, 'draft')


class DAGValidationTests(TestCase):
    """CI gate: ensure workflow/views/models import cleanly and URLs resolve (no cycles, no undefined refs)."""

    def test_import_voting_workflow_and_views(self):
        """Import critical modules to catch cycles and missing refs."""
        from voting import workflow  # noqa: F401
        from voting import views    # noqa: F401
        from voting import models  # noqa: F401
        self.assertTrue(hasattr(workflow, 'ELECTION_STATUS_TRANSITIONS'))
        self.assertTrue(hasattr(views, 'election_status_change'))

    def test_voting_urls_load(self):
        """All voting URL names resolve without error."""
        from django.urls import reverse
        reverse('voting:dashboard')
        reverse('voting:election_list')
        reverse('voting:status')
        reverse('voting:create_election')


class RoleAssignmentTogglePolicyTests(TestCase):
    """Role-toggle policy: role assignment excludes super_admin."""

    def setUp(self):
        User = get_user_model()
        self.super_admin = User.objects.create_superuser(
            email='root@example.com',
            first_name='Root',
            last_name='Admin',
            password='TestPass123!',
        )
        self.target_user = User.objects.create_user(
            email='member@example.com',
            first_name='Member',
            last_name='User',
            password='TestPass123!',
            role='voter',
        )
        self.other_super_admin = User.objects.create_superuser(
            email='root2@example.com',
            first_name='Root',
            last_name='Two',
            password='TestPass123!',
        )

    def test_super_admin_toggle_does_not_offer_super_admin_role(self):
        self.client.login(email='root@example.com', password='TestPass123!')
        resp = self.client.get(reverse('voting:user_detail', args=[self.target_user.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Role toggle')
        self.assertNotContains(resp, 'value="super_admin"')

    def test_cannot_assign_super_admin_role_from_toggle_endpoint(self):
        self.client.login(email='root@example.com', password='TestPass123!')
        resp = self.client.post(
            reverse('voting:user_change_role', args=[self.target_user.pk]),
            data={'role': 'super_admin'},
        )
        self.assertEqual(resp.status_code, 302)
        self.target_user.refresh_from_db()
        self.assertEqual(self.target_user.role, 'voter')

    def test_super_admin_target_role_is_not_editable_in_toggle_flow(self):
        self.client.login(email='root@example.com', password='TestPass123!')
        resp = self.client.post(
            reverse('voting:user_change_role', args=[self.other_super_admin.pk]),
            data={'role': 'auditor'},
        )
        self.assertEqual(resp.status_code, 302)
        self.other_super_admin.refresh_from_db()
        self.assertEqual(self.other_super_admin.role, 'super_admin')


@override_settings(SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class CandidatePrivacyIsolationTests(TestCase):
    """Candidate management pages must be isolated per manageable election scope."""

    def setUp(self):
        User = get_user_model()
        self.creator_a = User.objects.create_user(
            email='creator-a@example.com',
            first_name='Creator',
            last_name='A',
            password='TestPass123!',
            role='election_admin',
        )
        self.creator_b = User.objects.create_user(
            email='creator-b@example.com',
            first_name='Creator',
            last_name='B',
            password='TestPass123!',
            role='election_admin',
        )
        start = timezone.now()
        end = start + timezone.timedelta(days=1)
        self.election_a = Election.objects.create(
            title='Election A',
            description='Desc',
            election_type='general',
            voting_type='single_choice',
            status='draft',
            start_date=start,
            end_date=end,
            creator=self.creator_a,
        )
        self.ballot_a = Ballot.objects.create(
            election=self.election_a,
            title='Ballot A',
            question='Question A?',
            order=1,
        )
        self.candidate_a = Candidate.objects.create(
            ballot=self.ballot_a,
            name='Candidate A1',
            order=1,
        )

    def test_other_creator_cannot_see_candidate_in_list(self):
        self.client.login(email='creator-b@example.com', password='TestPass123!')
        resp = self.client.get(reverse('voting:candidate_list'))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'Candidate A1')
        page_obj = resp.context['page_obj']
        self.assertEqual(page_obj.paginator.count, 0)

    def test_other_creator_cannot_open_candidate_detail(self):
        self.client.login(email='creator-b@example.com', password='TestPass123!')
        resp = self.client.get(reverse('voting:candidate_detail', args=[self.candidate_a.pk]))
        self.assertEqual(resp.status_code, 404)

    def test_create_candidate_form_ballots_are_scoped(self):
        start = timezone.now()
        end = start + timezone.timedelta(days=1)
        election_b = Election.objects.create(
            title='Election B',
            description='Desc',
            election_type='general',
            voting_type='single_choice',
            status='draft',
            start_date=start,
            end_date=end,
            creator=self.creator_b,
        )
        ballot_b = Ballot.objects.create(
            election=election_b,
            title='Ballot B',
            question='Question B?',
            order=1,
        )
        self.client.login(email='creator-b@example.com', password='TestPass123!')
        resp = self.client.get(reverse('voting:create_candidate'))
        self.assertEqual(resp.status_code, 200)
        ballot_field = resp.context['form'].fields['ballot']
        self.assertEqual(list(ballot_field.queryset), [ballot_b])


@override_settings(SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class ElectionPrivacyIsolationTests(TestCase):
    """Election views should block cross-creator access for election admins."""

    def setUp(self):
        User = get_user_model()
        self.creator_a = User.objects.create_user(
            email='election-a@example.com',
            first_name='Election',
            last_name='A',
            password='TestPass123!',
            role='election_admin',
        )
        self.creator_b = User.objects.create_user(
            email='election-b@example.com',
            first_name='Election',
            last_name='B',
            password='TestPass123!',
            role='election_admin',
        )
        start = timezone.now()
        end = start + timezone.timedelta(days=1)
        self.election_a = Election.objects.create(
            title='Private Election A',
            description='Desc',
            election_type='general',
            voting_type='single_choice',
            status='draft',
            start_date=start,
            end_date=end,
            creator=self.creator_a,
        )
        self.ballot_a = Ballot.objects.create(
            election=self.election_a,
            title='Private Ballot A',
            question='Question A?',
            order=1,
        )
        self.candidate_a = Candidate.objects.create(
            ballot=self.ballot_a,
            name='Private Candidate A',
            order=1,
        )

    def test_other_creator_cannot_access_election_detail_by_url(self):
        self.client.login(email='election-b@example.com', password='TestPass123!')
        resp = self.client.get(reverse('voting:election_detail', args=[self.election_a.pk]))
        self.assertEqual(resp.status_code, 302)

    def test_other_creator_cannot_access_election_results_by_url(self):
        self.client.login(email='election-b@example.com', password='TestPass123!')
        resp = self.client.get(reverse('voting:election_results', args=[self.election_a.pk]))
        self.assertEqual(resp.status_code, 302)

    def test_other_creator_cannot_access_ballot_results_by_url(self):
        self.client.login(email='election-b@example.com', password='TestPass123!')
        resp = self.client.get(reverse('voting:ballot_results', args=[self.ballot_a.pk]))
        self.assertEqual(resp.status_code, 302)

    def test_other_creator_does_not_see_private_election_in_election_list(self):
        self.client.login(email='election-b@example.com', password='TestPass123!')
        resp = self.client.get(reverse('voting:election_list'))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'Private Election A')

    def test_owner_still_can_access_own_election_detail(self):
        self.client.login(email='election-a@example.com', password='TestPass123!')
        resp = self.client.get(reverse('voting:election_detail', args=[self.election_a.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Private Election A')


@override_settings(SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class ElectionApiPrivacyTests(TestCase):
    """API election list should be authenticated and creator-scoped for election admins."""

    def setUp(self):
        User = get_user_model()
        self.creator_a = User.objects.create_user(
            email='api-a@example.com',
            first_name='Api',
            last_name='A',
            password='TestPass123!',
            role='election_admin',
        )
        self.creator_b = User.objects.create_user(
            email='api-b@example.com',
            first_name='Api',
            last_name='B',
            password='TestPass123!',
            role='election_admin',
        )
        start = timezone.now()
        end = start + timezone.timedelta(days=1)
        self.election_a = Election.objects.create(
            title='API Election A',
            description='Desc',
            election_type='general',
            voting_type='single_choice',
            status='draft',
            start_date=start,
            end_date=end,
            creator=self.creator_a,
        )
        self.election_b = Election.objects.create(
            title='API Election B',
            description='Desc',
            election_type='general',
            voting_type='single_choice',
            status='draft',
            start_date=start,
            end_date=end,
            creator=self.creator_b,
        )

    def test_api_requires_authentication(self):
        resp = self.client.get(reverse('voting:api-election-list'))
        self.assertIn(resp.status_code, (401, 403))

    def test_api_returns_paginated_payload(self):
        self.client.login(email='api-a@example.com', password='TestPass123!')
        resp = self.client.get(reverse('voting:api-election-list'))
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertIn('count', payload)
        self.assertIn('results', payload)
        self.assertEqual(payload['count'], 1)

    def test_api_enforces_creator_scope_for_election_admin(self):
        self.client.login(email='api-b@example.com', password='TestPass123!')
        resp = self.client.get(reverse('voting:api-election-list'))
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        titles = {item['title'] for item in payload['results']}
        self.assertIn('API Election B', titles)
        self.assertNotIn('API Election A', titles)


@override_settings(SECURE_SSL_REDIRECT=False, SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class UserListFilteringTests(TestCase):
    """User list should support search and per-page controls."""

    def setUp(self):
        User = get_user_model()
        self.super_admin = User.objects.create_superuser(
            email='ul-root@example.com',
            first_name='Root',
            last_name='User',
            password='TestPass123!',
        )
        User.objects.create_user(
            email='alice@example.com',
            first_name='Alice',
            last_name='Wright',
            password='TestPass123!',
            role='voter',
        )
        User.objects.create_user(
            email='bob@example.com',
            first_name='Bob',
            last_name='Stone',
            password='TestPass123!',
            role='monitor',
        )

    def test_user_list_search_filters_by_email_or_name(self):
        self.client.login(email='ul-root@example.com', password='TestPass123!')
        resp = self.client.get(reverse('voting:user_list'), data={'search': 'alice'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'alice@example.com')
        self.assertNotContains(resp, 'bob@example.com')

    def test_user_list_respects_per_page_parameter(self):
        self.client.login(email='ul-root@example.com', password='TestPass123!')
        resp = self.client.get(reverse('voting:user_list'), data={'per_page': '10'})
        self.assertEqual(resp.status_code, 200)
        page_obj = resp.context['page_obj']
        self.assertEqual(page_obj.paginator.per_page, 10)

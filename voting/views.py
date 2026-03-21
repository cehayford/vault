from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.conf import settings
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from django.http import HttpResponse
from django.db import IntegrityError
from django.db.models import Max
from userauth.decorators import require_role, require_org_membership, require_not_voter
from .models import (
    Election, Ballot, Candidate, Vote, VoteReceipt,
    VotingSession, EligibleVoter, VoteChainEntry,
    Organisation, OrgMembership,
)
from .forms import ElectionForm, BallotForm, CandidateForm, OrganisationForm
from .workflow import ELECTION_STATUS_TRANSITIONS, is_definition_sealed
import uuid
from userauth.models import SecurityLog
from collections import Counter
from itertools import groupby
from reportlab.lib.pagesizes import letter
from .models import EligibleVoter
from .tasks import send_voter_invite_notification
import csv
import io
from .models import VoteChainEntry
from .models import VoteReceipt, VoteChainEntry
import logging
import base64
from io import BytesIO
import qrcode
from .tasks import send_share_link_to_recipients
from django.db.models import Max
from django.contrib.auth import get_user_model
from userauth.models import SecurityLog
from django.core.paginator import Paginator


def can_manage_election(election, user):
    """True if user may edit/invite/export/delete this election (uses Election.user_can_manage)."""
    if not user.is_authenticated:
        return False
    return getattr(election, 'user_can_manage', lambda u: False)(user)


@login_required
def dashboard(request):
    """Main voting dashboard; stats and recent elections are tenant-filtered for non–super_admins."""
    user = request.user
    elections_qs = _elections_for_user(request)
    active_elections = elections_qs.filter(status='active').count()
    votes_cast = Vote.objects.filter(voter=user).count()
    pending_elections = elections_qs.filter(status='scheduled').count()
    completed_elections = elections_qs.filter(status='completed').count()
    total_votes = Vote.objects.count()
    from django.contrib.auth import get_user_model
    User = get_user_model()
    verified_users = User.objects.filter(is_verified=True).count()
    context = {
        'user': user,
        'active_elections': active_elections,
        'votes_cast': votes_cast,
        'pending_elections': pending_elections,
        'completed_elections': completed_elections,
        'recent_elections': list(elections_qs[:5]),
        'verified_users': verified_users,
        'total_votes': total_votes,
    }
    return render(request, 'voting/dashboard.html', context)


@login_required
def status_view(request):
    """Status page: account status for all; election status summary for admins."""
    user = request.user
    elections_qs = _elections_for_user(request)
    by_status = {}
    for status_key, _ in Election.STATUS_CHOICES:
        by_status[status_key] = elections_qs.filter(status=status_key).count()
    context = {
        'user': user,
        'elections_by_status': by_status,
        'total_elections': elections_qs.count(),
        'can_manage_any': user.role in ('super_admin', 'election_admin', 'org_admin'),
    }
    return render(request, 'voting/status.html', context)


def _elections_for_user(request):
    """Elections visible to current user: super_admin sees all; org_admin sees their orgs'; others tenant or null."""
    from django.db.models import Q
    qs = Election.objects.select_related('creator', 'tenant', 'organisation').order_by('-created_at')
    role = getattr(request.user, 'role', None)
    if role == 'super_admin':
        return qs
    if role == 'org_admin':
        org_ids = request.user.org_memberships.filter(is_active=True).values_list('organisation_id', flat=True)
        return qs.filter(Q(organisation_id__in=org_ids) | Q(creator=request.user))
    user_tenant = getattr(request.user, 'tenant', None)
    return qs.filter(Q(tenant=user_tenant) | Q(tenant__isnull=True))


@login_required
def election_list(request):
    """List all elections with optional filter and pagination. Tenant isolation: non-super_admin see only their tenant (or null)."""
    from django.db.models import Q
    from django.core.paginator import Paginator
    from .forms import ElectionFilterForm
    elections = _elections_for_user(request)
    form = ElectionFilterForm(request.GET or None)
    if form.is_valid():
        if form.cleaned_data.get('status'):
            elections = elections.filter(status=form.cleaned_data['status'])
        if form.cleaned_data.get('search'):
            q = form.cleaned_data['search']
            elections = elections.filter(Q(title__icontains=q) | Q(description__icontains=q))
    try:
        per_page = max(10, min(100, int(request.GET.get('per_page') or 20)))
    except (TypeError, ValueError):
        per_page = 20
    paginator = Paginator(elections, per_page)
    page_obj = paginator.get_page(request.GET.get('page'))
    get_copy = request.GET.copy()
    get_copy.pop('page', None)
    get_copy.pop('per_page', None)
    pagination_query = get_copy.urlencode()
    can_create_election = request.user.role in ('super_admin', 'election_admin', 'org_admin')
    return render(request, 'voting/election_list.html', {
        'page_obj': page_obj,
        'form': form,
        'pagination_query': pagination_query,
        'can_create_election': can_create_election,
    })


@login_required
@require_not_voter
def create_election(request):
    """Create a new election (Creator = super_admin or election_admin or org_admin)."""
    if request.user.role not in ('super_admin', 'election_admin', 'org_admin'):
        messages.error(request, 'You do not have permission to create elections.')
        return redirect('voting:dashboard')
    if request.method == 'POST':
        form = ElectionForm(request.POST)
        if form.is_valid():
            election = form.save(commit=False)
            election.creator = request.user
            election.tenant = getattr(request.user, 'tenant', None)
            # If the user is an OrgAdmin with at least one organisation, default to the first active org.
            if getattr(request.user, 'role', None) == 'org_admin':
                membership = request.user.org_memberships.filter(is_active=True).select_related('organisation').first()
                if membership:
                    election.organisation = membership.organisation
            election.save()
            messages.success(request, 'Election created successfully!')
            return redirect('voting:election_detail', pk=election.pk)
    else:
        form = ElectionForm()
    return render(request, 'voting/create_election.html', {'form': form})


@login_required
@require_not_voter
@require_role('super_admin', 'election_admin', 'org_admin')
def create_organisation(request):
    """Create a new organisation; elevates creator to org_admin if needed."""
    if request.method == 'POST':
        form = OrganisationForm(request.POST, request.FILES)
        if form.is_valid():
            org = form.save(commit=False)
            org.owner = request.user
            org.save()
            OrgMembership.objects.create(
                organisation=org,
                user=request.user,
                role='org_admin',
                invited_by=request.user,
            )
            if request.user.role not in ('org_admin', 'super_admin'):
                request.user.role = 'org_admin'
                request.user.save()
            messages.success(request, f'Organisation \"{org.name}\" created.')
            return redirect('voting:org_dashboard', org_slug=org.slug)
    else:
        form = OrganisationForm()
    return render(request, 'voting/create_organisation.html', {'form': form})


@login_required
@require_not_voter
@require_role('super_admin', 'org_admin')
@require_org_membership()
def org_dashboard(request, org_slug):
    """Minimal OrgAdmin dashboard scoped to a single organisation."""
    org = get_object_or_404(Organisation, slug=org_slug)
    elections = org.elections.select_related('creator').order_by('-created_at')
    members = org.memberships.filter(is_active=True).select_related('user')
    context = {
        'org': org,
        'elections': elections,
        'members': members,
        'total_elections': elections.count(),
        'active_elections': elections.filter(status='active').count(),
        'completed_elections': elections.filter(status='completed').count(),
    }
    return render(request, 'voting/org_dashboard.html', context)


@login_required
def election_detail(request, pk):
    """Display election details"""
    election = get_object_or_404(
        Election.objects.prefetch_related(
            'ballots__candidates',
        ),
        pk=pk,
    )
    # Auto-close: if end_date has passed and still marked active, set to closed so "ended" is consistent
    if election.status == 'active' and election.has_ended():
        election.status = 'closed'
        election.save(update_fields=['status', 'updated_at'])
    ballots = list(election.ballots.all())
    candidates = [c for b in ballots for c in b.candidates.all()]

    # Check if user can vote: only the creator is blocked; non-creators are allowed if otherwise eligible.
    creator_id = getattr(election, 'creator_id', None)
    if election.status != 'active' or not request.user.is_authenticated or not request.user.is_verified:
        user_can_vote = False
    elif creator_id is not None and request.user.pk == creator_id:
        user_can_vote = False  # Creator cannot vote in their own election
    elif EligibleVoter.objects.filter(
            election=election,
            email__iexact=request.user.email,
        ).exists():
        user_can_vote = True  # Invited via shareable link / invite list
    elif getattr(election, 'require_voter_registration', False):
        user_can_vote = False  # Registration required and not on list
    else:
        user_can_vote = request.user.eligibility_verified
    voted_ballot_ids = set()
    if ballots and request.user.is_authenticated:
        voted_ballot_ids = set(
            Vote.objects.filter(
                ballot__in=ballots,
                voter=request.user,
            ).values_list('ballot_id', flat=True)
        )
    for ballot in ballots:
        ballot.user_has_voted = ballot.pk in voted_ballot_ids
    votes_cast = Vote.objects.filter(ballot__election=election).count()
    total_voters = EligibleVoter.objects.filter(election=election).count()
    turnout_percentage = (votes_cast / total_voters * 100) if total_voters else None
    user_is_creator = creator_id is not None and request.user.pk == creator_id
    can_manage = can_manage_election(election, request.user)
    context = {
        'election': election,
        'ballots': ballots,
        'candidates': candidates,
        'user_can_vote': user_can_vote,
        'user_is_creator': user_is_creator,
        'can_manage': can_manage,
        'total_voters': total_voters,
        'votes_cast': votes_cast,
        'turnout_percentage': round(turnout_percentage, 1) if turnout_percentage is not None else None,
    }
    return render(request, 'voting/election_detail.html', context)


@login_required
@require_not_voter
def edit_election(request, pk):
    """Edit an existing election (creator or super_admin or election_admin or org_admin)."""
    election = get_object_or_404(Election, pk=pk)
    if not can_manage_election(election, request.user):
        messages.error(request, 'Access denied.')
        return redirect('voting:dashboard')
    if request.method == 'POST':
        form = ElectionForm(request.POST, instance=election)
        if form.is_valid():
            form.save()
            messages.success(request, 'Election updated successfully!')
            return redirect('voting:election_detail', pk=election.pk)
    else:
        form = ElectionForm(instance=election)
    return render(request, 'voting/edit_election.html', {'form': form, 'election': election})


@login_required
@require_not_voter
def add_ballot(request, election_id):
    """Add a ballot to an election (creator or super_admin or election_admin or org_admin). Only when definition is not sealed (draft)."""
    election = get_object_or_404(Election, pk=election_id)
    if not can_manage_election(election, request.user):
        messages.error(request, 'Access denied.')
        return redirect('voting:dashboard')
    if is_definition_sealed(election.status):
        messages.error(request, 'Cannot add ballots once the election is scheduled or active. Definition is sealed.')
        return redirect('voting:election_detail', pk=election.pk)
    if request.method == 'POST':
        form = BallotForm(request.POST)
        if form.is_valid():
            ballot = form.save(commit=False)
            ballot.election = election
            ballot.election_id = election.pk
            used_orders = set(election.ballots.values_list('order', flat=True))
            next_order = 0
            while next_order in used_orders:
                next_order += 1
            ballot.order = next_order
            try:
                ballot.save()
            except IntegrityError:
                # Rare race: recompute next free order and retry once
                used_orders = set(election.ballots.values_list('order', flat=True))
                next_order = 0
                while next_order in used_orders:
                    next_order += 1
                ballot.order = next_order
                try:
                    ballot.save()
                except IntegrityError:
                    messages.error(request, 'Could not add ballot. Please try again.')
                    return render(request, 'voting/add_ballot.html', {'form': form, 'election': election})
            messages.success(request, 'Ballot added successfully!')
            return redirect('voting:election_detail', pk=election.pk)
    else:
        form = BallotForm()
    return render(request, 'voting/add_ballot.html', {'form': form, 'election': election})


@login_required
@require_not_voter
def delete_ballot(request, pk):
    """Delete a ballot; requires can_manage on the election. Only when definition is not sealed (draft)."""
    ballot = get_object_or_404(Ballot.objects.select_related('election'), pk=pk)
    election = ballot.election
    if not can_manage_election(election, request.user):
        messages.error(request, 'Access denied.')
        return redirect('voting:dashboard')
    if is_definition_sealed(election.status):
        messages.error(request, 'Cannot remove ballots once the election is scheduled or active. Definition is sealed.')
        return redirect('voting:election_detail', pk=election.pk)
    if request.method == 'POST':
        ballot.delete()
        messages.success(request, 'Ballot removed.')
        return redirect('voting:election_detail', pk=election.pk)
    return redirect('voting:election_detail', pk=election.pk)


@login_required
@require_not_voter
def delete_election(request, pk):
    """Delete an election. Allowed only for draft (by manager) or any status (super_admin)."""
    election = get_object_or_404(Election, pk=pk)
    if not can_manage_election(election, request.user):
        messages.error(request, 'Access denied.')
        return redirect('voting:dashboard')
    if request.method != 'POST':
        return redirect('voting:election_detail', pk=pk)
    if request.user.role != 'super_admin' and election.status != 'draft':
        messages.error(request, 'Only draft elections can be deleted.')
        return redirect('voting:election_detail', pk=pk)
    title = election.title
    election.delete()
    messages.success(request, f'Election "{title}" has been deleted.')
    return redirect('voting:dashboard')


@login_required
@require_not_voter
def election_status_change(request, pk):
    """POST only: set election to next_status if allowed and user can manage."""
    election = get_object_or_404(Election, pk=pk)
    if not can_manage_election(election, request.user):
        messages.error(request, 'Access denied.')
        return redirect('voting:dashboard')
    if request.method != 'POST':
        return redirect('voting:election_detail', pk=pk)
    next_status = (request.POST.get('next_status') or '').strip().lower()
    allowed = ELECTION_STATUS_TRANSITIONS.get(election.status, ())
    if next_status not in allowed:
        messages.error(request, f'Cannot change status from {election.status} to {next_status}.')
        return redirect('voting:election_detail', pk=pk)
    if next_status in ('scheduled', 'active') and not election.ballots.exists():
        messages.error(request, 'Add at least one ballot before scheduling or opening the election.')
        return redirect('voting:election_detail', pk=pk)
    election.status = next_status
    election.save(update_fields=['status', 'updated_at'])
    messages.success(request, f'Election status set to {next_status}.')
    return redirect('voting:election_detail', pk=pk)


def _check_vote_eligibility(request, election, voter, ip):
    """Run eligibility checks. Returns (False, redirect_response) or (True, None). Only the creator is blocked; non-creators are allowed to vote if they pass other checks."""
    from userauth.models import SecurityLog
    if getattr(election, 'creator_id', None) is not None and voter.pk == election.creator_id:
        SecurityLog.objects.create(
            user=voter, action_type='vote_eligibility_denied',
            description=f'Election creator cannot vote in their own election {election.pk}',
            ip_address=ip, success=False,
        )
        messages.error(request, 'The election creator cannot vote in their own election.')
        return False, redirect('voting:election_detail', pk=election.pk)
    if not voter.is_verified:
        SecurityLog.objects.create(
            user=voter, action_type='vote_eligibility_denied',
            description='Unverified account attempted to vote', ip_address=ip, success=False,
        )
        return False, redirect('voting:dashboard')
    if getattr(election, 'require_mfa', False) and not getattr(voter, 'phone_verified', False):
        return False, redirect('userauth:phone_verify')
    allowed = getattr(election, 'allowed_email_domains', None)
    if allowed:
        domain = voter.email.split('@')[-1].lower() if voter.email else ''
        if domain not in [d.lower() for d in allowed]:
            SecurityLog.objects.create(
                user=voter, action_type='vote_eligibility_denied',
                description=f'Email domain not in allowlist for election {election.pk}',
                ip_address=ip, success=False,
            )
            return False, redirect('voting:dashboard')
    if getattr(election, 'require_voter_registration', False):
        try:
            ev = EligibleVoter.objects.get(election=election, email=voter.email)
            if ev.has_voted:
                return False, redirect('voting:election_detail', pk=election.pk)
        except EligibleVoter.DoesNotExist:
            SecurityLog.objects.create(
                user=voter, action_type='vote_eligibility_denied',
                description=f'Voter not on invite list for election {election.pk}',
                ip_address=ip, success=False,
            )
            return False, redirect('voting:dashboard')
    return True, None


def _parse_vote_selections(request, election, ballot):
    """Parse POST into list of selection ids. Returns (selections, None) or (None, redirect_response)."""
    voting_type = election.voting_type
    if voting_type == 'single_choice':
        cid = request.POST.get('candidate')
        if not cid or not ballot.candidates.filter(pk=cid).exists():
            return None, redirect('voting:vote_ballot', pk=ballot.pk)
        return [cid], None
    if voting_type == 'multiple_choice':
        selections = request.POST.getlist('candidates')
        valid = {str(c.pk) for c in ballot.candidates.all()}
        if not selections or not all(s in valid for s in selections):
            return None, redirect('voting:vote_ballot', pk=ballot.pk)
        max_sel = getattr(ballot, 'max_selections', 10)
        if len(selections) > max_sel:
            return None, redirect('voting:vote_ballot', pk=ballot.pk)
        return selections, None
    if voting_type == 'ranked_choice':
        selections = request.POST.getlist('ranked_choices')
        return (selections, None) if selections else (None, redirect('voting:vote_ballot', pk=ballot.pk))
    if voting_type == 'proportional':
        # Proportional representation: one vote per voter for one candidate (party/list); results allocated by share.
        cid = request.POST.get('candidate')
        if not cid or not ballot.candidates.filter(pk=cid).exists():
            return None, redirect('voting:vote_ballot', pk=ballot.pk)
        return [cid], None
    return None, redirect('voting:vote_ballot', pk=ballot.pk)


def _vote_ballot_impl(request, pk):
    """Inner implementation. Use vote_ballot (decorated) as entry point."""
    ballot = get_object_or_404(Ballot, pk=pk)
    election = ballot.election
    voter = request.user
    ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
    user_agent = (request.META.get('HTTP_USER_AGENT') or '')[:500]
    now = timezone.now()
    if request.method == 'POST' and getattr(request, 'limited', False):
        SecurityLog.objects.create(
            user=voter, action_type='vote_ratelimit_hit',
            description=f'Rate limit hit on ballot {ballot.pk}', ip_address=ip, success=False,
        )
        messages.error(request, 'Too many requests. Please wait before voting again.')
        return redirect('voting:election_detail', pk=election.pk)
    if election.status != 'active':
        messages.error(request, 'This election is not currently active.')
        return redirect('voting:election_detail', pk=election.pk)
    if not (election.start_date <= now <= election.end_date):
        messages.error(request, 'Voting window is closed.')
        return redirect('voting:election_detail', pk=election.pk)
    ok, redir = _check_vote_eligibility(request, election, voter, ip)
    if not ok:
        if redir and 'phone_verify' in str(getattr(redir, 'url', '')):
            request.session['vote_after_mfa'] = str(ballot.pk)
            messages.error(request, 'This election requires phone verification.')
        elif redir and getattr(redir, 'url', None) == reverse('voting:dashboard'):
            messages.error(request, 'You are not eligible to vote. Verify email and/or phone.')
        return redir
    if getattr(election, 'require_mfa', False) and getattr(voter, 'mfa_enabled', False):
        last_mfa = request.session.get('last_mfa_verify_ts')
        if not last_mfa or (now.timestamp() - last_mfa) > 300:
            request.session['vote_after_mfa'] = str(ballot.pk)
            messages.info(request, 'Please confirm your identity before voting.')
            return redirect('userauth:mfa_verify')
    if Vote.objects.filter(ballot=ballot, voter=voter).exists():
        SecurityLog.objects.create(
            user=voter, action_type='vote_duplicate_blocked',
            description=f'Duplicate vote attempt on ballot {ballot.pk}', ip_address=ip, success=False,
        )
        messages.warning(request, 'You have already voted on this ballot.')
        return redirect('voting:election_detail', pk=election.pk)

    try:
        vs, created = VotingSession.objects.get_or_create(
            user=voter, election=election,
            defaults={'session_key': request.session.session_key or '', 'ip_address': ip},
        )
    except Exception:
        vs, created = None, True
    if vs and not created and getattr(vs, 'completed', False):
        messages.warning(request, 'Your voting session for this election is complete.')
        return redirect('voting:election_detail', pk=election.pk)
    if request.method == 'GET':
        candidates = ballot.candidates.all().order_by('order')
        recaptcha_enterprise = getattr(settings, 'RECAPTCHA_ENTERPRISE_ENABLED', False)
        recaptcha_enabled = getattr(settings, 'RECAPTCHA_ENABLED', False)
        ctx = {
            'ballot': ballot, 'election': election, 'candidates': candidates,
            'hcaptcha_site_key': getattr(settings, 'HCAPTCHA_SITE_KEY', '') if not recaptcha_enterprise and not recaptcha_enabled else '',
            'recaptcha_enterprise_enabled': recaptcha_enterprise,
            'recaptcha_enterprise_site_key': getattr(settings, 'RECAPTCHA_ENTERPRISE_SITE_KEY', '') if recaptcha_enterprise else '',
            'recaptcha_enabled': recaptcha_enabled and not recaptcha_enterprise,
            'recaptcha_site_key': getattr(settings, 'RECAPTCHA_SITE_KEY', '') if recaptcha_enabled and not recaptcha_enterprise else '',
        }
        return render(request, 'voting/vote_ballot.html', ctx)
    if election.require_captcha:
        if getattr(settings, 'RECAPTCHA_ENTERPRISE_ENABLED', False):
            token = request.POST.get('g-recaptcha-response') or request.POST.get('h-captcha-response', '')
            try:
                from google.cloud import recaptchaenterprise_v1
                project_id = getattr(settings, 'RECAPTCHA_ENTERPRISE_PROJECT_ID', '')
                site_key = getattr(settings, 'RECAPTCHA_ENTERPRISE_SITE_KEY', '')
                if not token or not project_id or not site_key:
                    raise ValueError('Missing token or Enterprise config')
                client = recaptchaenterprise_v1.RecaptchaEnterpriseServiceClient()
                event = recaptchaenterprise_v1.Event(
                    token=token,
                    site_key=site_key,
                    expected_action='VOTE',
                )
                assessment = recaptchaenterprise_v1.Assessment(event=event)
                parent = f'projects/{project_id}'
                response = client.create_assessment(parent=parent, assessment=assessment)
                if not response.token_properties.valid or (response.risk_analysis and getattr(response.risk_analysis, 'score', 1.0) < 0.5):
                    SecurityLog.objects.create(
                        user=voter, action_type='vote_captcha_failed',
                        description=f'reCAPTCHA Enterprise failed on ballot {ballot.pk}', ip_address=ip, success=False,
                    )
                    messages.error(request, 'CAPTCHA verification failed. Please try again.')
                    return redirect('voting:vote_ballot', pk=ballot.pk)
            except ImportError:
                messages.error(request, 'CAPTCHA verification is not available. Please try again later.')
                return redirect('voting:vote_ballot', pk=ballot.pk)
            except Exception:
                SecurityLog.objects.create(
                    user=voter, action_type='vote_captcha_failed',
                    description=f'reCAPTCHA Enterprise error on ballot {ballot.pk}', ip_address=ip, success=False,
                )
                messages.error(request, 'CAPTCHA verification failed. Please try again.')
                return redirect('voting:vote_ballot', pk=ballot.pk)
        elif getattr(settings, 'HCAPTCHA_ENABLED', False):
            token = request.POST.get('h-captcha-response', '')
            try:
                import requests
                r = requests.post(
                    'https://hcaptcha.com/siteverify',
                    data={
                        'secret': getattr(settings, 'HCAPTCHA_SECRET_KEY', ''),
                        'response': token,
                        'remoteip': ip,
                    },
                    timeout=15,
                )
                if not r.json().get('success'):
                    SecurityLog.objects.create(
                        user=voter, action_type='vote_captcha_failed',
                        description=f'CAPTCHA failed on ballot {ballot.pk}', ip_address=ip, success=False,
                    )
                    messages.error(request, 'CAPTCHA verification failed. Please try again.')
                    return redirect('voting:vote_ballot', pk=ballot.pk)
            except Exception:
                messages.error(request, 'CAPTCHA verification failed. Please try again.')
                return redirect('voting:vote_ballot', pk=ballot.pk)
        elif getattr(settings, 'RECAPTCHA_ENABLED', False):
            token = request.POST.get('g-recaptcha-response', '')
            try:
                import requests
                r = requests.post(
                    'https://www.google.com/recaptcha/api/siteverify',
                    data={
                        'secret': getattr(settings, 'RECAPTCHA_SECRET_KEY', ''),
                        'response': token,
                        'remoteip': ip,
                    },
                    timeout=15,
                )
                result = r.json()
                if not result.get('success'):
                    SecurityLog.objects.create(
                        user=voter, action_type='vote_captcha_failed',
                        description=f'reCAPTCHA v2 failed on ballot {ballot.pk}', ip_address=ip, success=False,
                    )
                    messages.error(request, 'CAPTCHA verification failed. Please try again.')
                    return redirect('voting:vote_ballot', pk=ballot.pk)
            except Exception:
                SecurityLog.objects.create(
                    user=voter, action_type='vote_captcha_failed',
                    description=f'reCAPTCHA v2 error on ballot {ballot.pk}', ip_address=ip, success=False,
                )
                messages.error(request, 'CAPTCHA verification failed. Please try again.')
                return redirect('voting:vote_ballot', pk=ballot.pk)

    selections, redir = _parse_vote_selections(request, election, ballot)
    if redir:
        messages.error(request, 'Please make a valid selection.')
        return redir
    if not selections:
        messages.error(request, 'Please make a selection.')
        return redirect('voting:vote_ballot', pk=ballot.pk)

    vote = Vote(
        election=election,
        ballot=ballot,
        voter=voter,
        vote_token=uuid.uuid4().hex,
        ip_address=ip,
        user_agent=user_agent,
        is_verified=True,
    )
    try:
        vote.encrypt_selections(selections)
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception('Vote encryption failed (check ENCRYPTION_KEY): %s', e)
        messages.error(
            request,
            'Your vote could not be recorded due to a server configuration error. Please contact the administrator.',
        )
        return redirect('voting:vote_ballot', pk=ballot.pk)
    vote.save()
    receipt = VoteReceipt(vote=vote)
    receipt.save()
    vote.generate_verification_hash()
    try:
        VoteChainEntry.create_for_vote(vote)
    except Exception:
        pass
    if vs:
        try:
            vs.complete()
        except Exception:
            pass
    if getattr(election, 'require_voter_registration', False):
        try:
            ev = EligibleVoter.objects.get(election=election, email=voter.email)
            ev.mark_voted()
        except EligibleVoter.DoesNotExist:
            pass
    SecurityLog.objects.create(
        user=voter, action_type='vote_cast',
        description=f'Vote cast on ballot {ballot.pk} in election {election.pk}',
        ip_address=ip, success=True,
    )
    same_ip_others = Vote.objects.filter(
        election=election, ip_address=ip,
    ).exclude(voter=voter).exists()
    if same_ip_others:
        SecurityLog.objects.create(
            user=voter, action_type='suspicious_ip',
            description=f'Multiple voters from IP {ip} in election {election.pk}. Voter: {voter.email}',
            ip_address=ip, success=True,
        )
    try:
        from .tasks import send_vote_confirmation_email, flag_suspicious_voting_activity
        send_vote_confirmation_email.delay(
            voter_email=voter.email,
            election_title=election.title,
            receipt_code=receipt.receipt_code,
        )
        flag_suspicious_voting_activity.apply_async(args=[str(election.pk)], countdown=60)
    except Exception:
        pass
    messages.success(
        request,
        f'Your vote has been recorded. Receipt code: {receipt.receipt_code} — check your email for confirmation.',
    )
    return redirect('voting:election_detail', pk=election.pk)


try:
    from django_ratelimit.decorators import ratelimit
except ImportError:
    def ratelimit(*args, **kwargs):
        def noop(f):
            return f
        return noop


@login_required
@ratelimit(key='user', rate='3/m', method='POST', block=False)
@ratelimit(key='ip', rate='10/m', method='POST', block=False)
def vote_ballot(request, pk):
    """Entry point: rate-limited, then delegates to _vote_ballot_impl."""
    return _vote_ballot_impl(request, pk)


@login_required
def ballot_results(request, pk):
    """Display ballot results from encrypted votes. For proportional elections, optionally show seat allocation."""
    ballot = get_object_or_404(Ballot, pk=pk)
    election = ballot.election
    votes = Vote.objects.filter(ballot=ballot)
    counter = Counter()
    for vote in votes:
        try:
            for sel in vote.decrypt_selections():
                counter[sel] += 1
        except Exception:
            continue
    total = sum(counter.values())
    candidates = list(ballot.candidates.all().order_by('order'))
    results_list = [
        {'candidate': c, 'count': counter.get(str(c.pk), 0)}
        for c in candidates
    ]
    if total:
        for r in results_list:
            r['pct'] = round(100 * r['count'] / total, 1)
    else:
        for r in results_list:
            r['pct'] = 0
    # Proportional representation: allocate seats by largest remainder when ballot has seats > 1
    seats_map = {}
    if getattr(election, 'voting_type', None) == 'proportional':
        num_seats = getattr(ballot, 'seats', None)
        if num_seats is not None and num_seats > 1:
            from .proportional import allocate_seats_largest_remainder
            candidate_votes = {str(c.pk): counter.get(str(c.pk), 0) for c in candidates}
            seats_map = allocate_seats_largest_remainder(candidate_votes, num_seats)
    for r in results_list:
        r['seats'] = seats_map.get(str(r['candidate'].pk), 0)
    max_count = max((r['count'] for r in results_list), default=0)
    return render(request, 'voting/ballot_results.html', {
        'ballot': ballot,
        'election': election,
        'results_list': results_list,
        'total_votes': total,
        'max_count': max_count,
        'is_proportional': getattr(election, 'voting_type', None) == 'proportional',
        'total_seats': getattr(ballot, 'seats', None) if getattr(election, 'voting_type', None) == 'proportional' else None,
    })


@login_required
def election_results(request, pk):
    """Display election results"""
    election = get_object_or_404(Election, pk=pk)
    ballots = election.ballots.all()
    total_votes = Vote.objects.filter(election=election).count()
    total_voters = Vote.objects.filter(election=election).values('voter').distinct().count()
    turnout_percentage = None
    if election.require_voter_registration:
        eligible_count = election.eligible_voters.count()
        if eligible_count:
            turnout_percentage = round(100 * total_voters / eligible_count, 1)
    return render(request, 'voting/election_results.html', {
        'election': election,
        'ballots': ballots,
        'total_votes': total_votes,
        'total_voters': total_voters,
        'turnout_percentage': turnout_percentage,
    })


def _election_results_export_data(election):
    """Build list of rows for CSV/PDF: per ballot, per candidate with votes and pct."""
    rows = []
    votes_qs = Vote.objects.filter(election=election)
    for ballot in election.ballots.all().order_by('order', 'id'):
        votes = votes_qs.filter(ballot=ballot)
        counter = Counter()
        for vote in votes:
            try:
                for sel in vote.decrypt_selections():
                    counter[sel] += 1
            except Exception:
                continue
        total = sum(counter.values())
        for c in ballot.candidates.all().order_by('order', 'id'):
            count = counter.get(str(c.pk), 0)
            pct = round(100 * count / total, 1) if total else 0
            rows.append({
                'election_title': election.title,
                'ballot_title': ballot.title,
                'candidate_name': c.name,
                'votes': count,
                'pct': pct,
            })
    return rows


@login_required
@require_not_voter
def export_election_results_csv(request, pk):
    """Export election results as CSV. Creator or super_admin or election_admin or org_admin."""
    election = get_object_or_404(Election, pk=pk)
    if not can_manage_election(election, request.user):
        messages.error(request, 'Access denied.')
        return redirect('voting:election_results', pk=pk)
    rows = _election_results_export_data(election)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(['Election', 'Ballot', 'Candidate', 'Votes', 'Percentage'])
    for r in rows:
        writer.writerow([r['election_title'], r['ballot_title'], r['candidate_name'], r['votes'], r['pct']])
    response = HttpResponse(buf.getvalue(), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="election-{election.pk}-results.csv"'
    return response


@login_required
@require_not_voter
def export_election_results_pdf(request, pk):
    """Export election results as PDF. Creator or super_admin or election_admin or org_admin."""
    election = get_object_or_404(Election, pk=pk)
    if not can_manage_election(election, request.user):
        messages.error(request, 'Access denied.')
        return redirect('voting:election_results', pk=pk)
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib import colors
    except ImportError:
        messages.error(request, 'PDF export is not available (reportlab not installed).')
        return redirect('voting:election_results', pk=pk)
    rows = _election_results_export_data(election)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter)
    styles = getSampleStyleSheet()
    story = [
        Paragraph(f"Results: {election.title}", styles['Title']),
        Spacer(1, 12),
    ]
    # Group by ballot
    for ballot_title, group in groupby(rows, key=lambda r: r['ballot_title']):
        story.append(Paragraph(ballot_title, styles['Heading2']))
        story.append(Spacer(1, 6))
        table_data = [['Candidate', 'Votes', '%']]
        for r in group:
            table_data.append([r['candidate_name'], str(r['votes']), str(r['pct'])])
        t = Table(table_data)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ]))
        story.append(t)
        story.append(Spacer(1, 16))
    doc.build(story)
    response = HttpResponse(buf.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="election-{election.pk}-results.pdf"'
    return response


@login_required
@require_not_voter
def admin_dashboard(request):
    """Admin dashboard for system management"""
    if request.user.role not in ('super_admin', 'election_admin', 'org_admin'):
        messages.error(request, 'You do not have permission to access the admin dashboard.')
        return redirect('voting:dashboard')
    
    from userauth.models import CustomUser, SecurityLog

    elections_qs = _elections_for_user(request)
    context = {
        'total_users': CustomUser.objects.count(),
        'verified_users': CustomUser.objects.filter(is_verified=True).count(),
        'active_elections': elections_qs.filter(status='active').count(),
        'total_votes': Vote.objects.count(),
        'pending_elections': elections_qs.filter(status='scheduled').count(),
        'completed_elections': elections_qs.filter(status='completed').count(),
        'recent_security_events': SecurityLog.objects.select_related('user').order_by('-timestamp')[:10],
        'recent_elections': elections_qs[:5],
        'elections_by_status': {
            s: elections_qs.filter(status=s).count()
            for s, _ in Election.STATUS_CHOICES
        },
        'suspicious_flags': SecurityLog.objects.filter(
            action_type='suspicious_ip'
        ).order_by('-timestamp')[:5],
    }
    return render(request, 'voting/admin_dashboard.html', context)


def _users_queryset_for_request(request):
    """Users visible to current user: super_admin sees all; org_admin sees org members only."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    if getattr(request.user, 'role', None) == 'super_admin':
        return User.objects.all().order_by('-account_created_at')
    if getattr(request.user, 'role', None) == 'org_admin':
        org_ids = OrgMembership.objects.filter(
            user=request.user, is_active=True
        ).values_list('organisation_id', flat=True)
        return User.objects.filter(
            org_memberships__organisation_id__in=org_ids,
            org_memberships__is_active=True,
        ).distinct().order_by('-account_created_at')
    return User.objects.none()


def _allowed_role_values_for_actor(actor_role, role_choices):
    """Roles the current actor may assign via the role-toggle template."""
    if actor_role == 'super_admin':
        # High-level policy: assignment flow excludes super_admin.
        return [role for role, _ in role_choices if role != 'super_admin']
    if actor_role == 'org_admin':
        return ['voter', 'auditor', 'monitor']
    return []


@login_required
@require_not_voter
def user_list(request):
    """List users for role management. Super_admin: all; org_admin: org members only."""
    if request.user.role not in ('super_admin', 'org_admin'):
        messages.error(request, 'You do not have permission to manage users.')
        return redirect('voting:dashboard')
    User = get_user_model()
    qs = _users_queryset_for_request(request)
    role_filter = request.GET.get('role', '').strip()
    if role_filter:
        qs = qs.filter(role=role_filter)
    verified_filter = request.GET.get('verified', '')
    if verified_filter == '1':
        qs = qs.filter(is_verified=True)
    elif verified_filter == '0':
        qs = qs.filter(is_verified=False)
    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    get_copy = request.GET.copy()
    get_copy.pop('page', None)
    pagination_query = get_copy.urlencode()
    can_assign_roles = request.user.role in ('super_admin', 'org_admin')
    return render(request, 'voting/user_list.html', {
        'page_obj': page_obj,
        'pagination_query': pagination_query,
        'can_assign_roles': can_assign_roles,
        'role_choices': User.ROLE_CHOICES,
    })


@login_required
@require_not_voter
def user_detail(request, pk):
    """View user and change role. Super_admin: any user; org_admin: org members only."""
    if request.user.role not in ('super_admin', 'org_admin'):
        messages.error(request, 'You do not have permission to view this user.')
        return redirect('voting:dashboard')
    User = get_user_model()
    user = get_object_or_404(User, pk=pk)
    qs = _users_queryset_for_request(request)
    if not qs.filter(pk=user.pk).exists():
        messages.error(request, 'You do not have permission to view this user.')
        return redirect('voting:user_list')
    can_change_role = request.user.role in ('super_admin', 'org_admin') and user.role != 'super_admin'
    role_choices_dict = dict(User.ROLE_CHOICES)
    allowed_values = _allowed_role_values_for_actor(request.user.role, User.ROLE_CHOICES)
    allowed_roles = [(role, role_choices_dict.get(role, role)) for role in allowed_values]
    return render(request, 'voting/user_detail.html', {
        'target_user': user,
        'can_change_role': can_change_role,
        'allowed_role_choices': allowed_roles,
        'is_super_admin_target': user.role == 'super_admin',
    })


@login_required
@require_not_voter
@require_http_methods(['POST'])
def user_change_role(request, pk):
    """Change a user's role. Super_admin: any role; org_admin: auditor, monitor, voter only for org members."""
    if request.user.role not in ('super_admin', 'org_admin'):
        messages.error(request, 'Access denied.')
        return redirect('voting:dashboard')
    User = get_user_model()
    user = get_object_or_404(User, pk=pk)
    qs = _users_queryset_for_request(request)
    if not qs.filter(pk=user.pk).exists():
        messages.error(request, 'You do not have permission to change this user.')
        return redirect('voting:user_list')
    if user.role == 'super_admin':
        messages.error(request, 'Super Admin role cannot be changed from this template.')
        return redirect('voting:user_detail', pk=pk)
    new_role = (request.POST.get('role') or '').strip()
    if not new_role:
        messages.error(request, 'No role selected.')
        return redirect('voting:user_detail', pk=pk)
    allowed_roles = _allowed_role_values_for_actor(request.user.role, User.ROLE_CHOICES)
    if new_role not in allowed_roles:
        messages.error(request, 'You cannot assign that role.')
        return redirect('voting:user_detail', pk=pk)
    if request.user.role == 'super_admin' and user.pk == request.user.pk and new_role != 'super_admin':
        messages.error(request, 'You cannot demote yourself from super_admin.')
        return redirect('voting:user_detail', pk=pk)
    old_role = user.role
    user.role = new_role
    user.save(update_fields=['role'])
    SecurityLog.objects.create(
        user=user,
        action_type='role_change',
        description=f'Role changed from {old_role} to {new_role} by {request.user.email}',
        ip_address=getattr(request, 'META', {}).get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
        success=True,
    )
    messages.success(request, f'Role updated to {new_role}.')
    return redirect('voting:user_detail', pk=pk)


@login_required
@require_not_voter
def audit_logs(request):
    """Display audit logs"""
    if request.user.role not in ('super_admin', 'auditor'):
        messages.error(request, 'Access denied.')
        return redirect('voting:dashboard')
    logs = SecurityLog.objects.select_related('user').order_by('-timestamp')
    if request.GET.get('action'):
        logs = logs.filter(action_type=request.GET.get('action'))
    audit_entries = Paginator(logs, 50).get_page(request.GET.get('page'))
    return render(request, 'voting/audit_logs.html', {
        'audit_entries': audit_entries,
        'action_types': SecurityLog.ACTION_TYPES,
    })


@login_required
def my_votes(request):
    """Display user's voting history with pagination (default 20 per page)."""
    votes = Vote.objects.filter(voter=request.user).select_related(
        'election', 'ballot'
    ).prefetch_related('votereceipt').order_by('-cast_at')
    paginator = Paginator(votes, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'voting/my_votes.html', {'page_obj': page_obj})


@login_required
def candidate_list(request):
    """List candidates with pagination; optionally scoped by ballot_id and/or election_id (GET params)."""
    qs = Candidate.objects.select_related('ballot', 'ballot__election').order_by(
        'ballot__election__title', 'ballot__order', 'ballot__title', 'order', 'name'
    )
    ballot_id = request.GET.get('ballot_id', '').strip()
    election_id = request.GET.get('election_id', '').strip()
    election = None
    ballot = None
    if ballot_id:
        try:
            ballot = get_object_or_404(Ballot, pk=ballot_id)
            qs = qs.filter(ballot=ballot)
            election = ballot.election
        except (ValueError, TypeError):
            qs = qs.none()
    if election_id:
        qs = qs.filter(ballot__election_id=election_id)
        if election is None and qs.exists():
            election = qs.first().ballot.election
    try:
        per_page = max(10, min(100, int(request.GET.get('per_page') or 25)))
    except (TypeError, ValueError):
        per_page = 25
    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(request.GET.get('page'))
    get_copy = request.GET.copy()
    get_copy.pop('page', None)
    get_copy.pop('per_page', None)
    pagination_query = get_copy.urlencode()
    can_manage_candidates = _user_can_manage_candidates(request.user)
    return render(request, 'voting/candidate_list.html', {
        'page_obj': page_obj,
        'election': election,
        'ballot': ballot,
        'can_manage_candidates': can_manage_candidates,
        'pagination_query': pagination_query,
    })


def _user_can_manage_candidates(user):
    """True if user can manage at least one election (super_admin, election_admin, org_admin, or creator)."""
    if user.role in ('super_admin', 'election_admin', 'org_admin'):
        return True
    return Election.objects.filter(creator=user).exists()


@login_required
@require_not_voter
def create_candidate(request):
    """Create a new candidate. Allowed: super_admin, election_admin, org_admin, or election creator (not voters)."""
    if not _user_can_manage_candidates(request.user):
        messages.error(request, 'You do not have permission to create candidates.')
        return redirect('voting:dashboard')
    if request.method == 'POST':
        form = CandidateForm(request.POST, request.FILES)
        if form.is_valid():
            ballot = form.cleaned_data.get('ballot')
            if ballot:
                election = ballot.election
                if not can_manage_election(election, request.user):
                    messages.error(request, 'Access denied.')
                    return redirect('voting:dashboard')
                if is_definition_sealed(election.status):
                    messages.error(request, 'Cannot add candidates once the election is scheduled or active. Definition is sealed.')
                    return redirect('voting:candidate_list')
            candidate = form.save(commit=False)
            # Assign next order to satisfy unique_together (ballot, order)
            last = Candidate.objects.filter(ballot=candidate.ballot).aggregate(Max('order'))['order__max']
            candidate.order = (last or 0) + 1
            candidate.save()
            messages.success(request, 'Candidate created successfully!')
            return redirect('voting:candidate_detail', pk=candidate.pk)
    else:
        form = CandidateForm()
    return render(request, 'voting/create_candidate.html', {'form': form})


@login_required
def candidate_detail(request, pk):
    """Display candidate details"""
    candidate = get_object_or_404(Candidate, pk=pk)
    return render(request, 'voting/candidate_detail.html', {'candidate': candidate})


def vote_by_invite(request, invite_token):
    """
    Shareable vote link: validate invite token, require login with matching email, redirect to election.
    If not logged in, show landing with Log in / Sign up (so voters can sign up from their invite link).
    """
    ev = get_object_or_404(EligibleVoter, invite_token=invite_token)
    election = ev.election
    if ev.has_voted:
        return render(request, 'voting/vote_by_invite.html', {
            'election': election,
            'already_voted': True,
            'invite_email': ev.email,
        })
    if not request.user.is_authenticated:
        invite_url = request.build_absolute_uri(request.get_full_path())
        return render(request, 'voting/vote_by_invite.html', {
            'election': election,
            'invite_email': ev.email,
            'already_voted': False,
            'show_login_signup': True,
            'invite_url': invite_url,
        })
    if request.user.email.lower() != ev.email.lower():
        messages.error(
            request,
            f'This invite link is for {ev.email}. Please log in with that email to vote.',
        )
        login_url = reverse('userauth:login')
        return redirect(f'{login_url}?next={request.get_full_path()}')
    # Send voter directly to the voting (ballot) page, not the election detail page
    ballots = list(election.ballots.all())
    if not ballots:
        return redirect('voting:election_detail', pk=election.pk)
    # First ballot they haven't voted on, or first ballot if they've voted on none
    for ballot in ballots:
        if not Vote.objects.filter(ballot=ballot, voter=request.user).exists():
            return redirect('voting:vote_ballot', pk=ballot.pk)
    return redirect('voting:election_detail', pk=election.pk)


def _parse_bulk_emails(raw):
    """Parse textarea into list of valid email strings (lowercased)."""
    if not raw:
        return []
    seen = set()
    out = []
    for part in raw.replace(',', '\n').splitlines():
        addr = part.strip().lower()
        if addr and '@' in addr and addr not in seen:
            seen.add(addr)
            out.append(addr)
    return out


def _parse_bulk_phones(raw):
    """Parse textarea into list of phone strings (digits/plus only, non-empty)."""
    if not raw:
        return []
    seen = set()
    out = []
    for part in raw.replace(',', '\n').splitlines():
        p = ''.join(c for c in part.strip() if c in '0123456789+').strip() or part.strip()
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return out


@login_required
@require_not_voter
def shareable_link(request, pk):
    """Shareable link for an election: copy, QR, and send by email/SMS to bulk recipients."""
    election = get_object_or_404(Election, pk=pk)
    if not can_manage_election(election, request.user):
        messages.error(request, 'Access denied.')
        return redirect('voting:dashboard')
    share_url = request.build_absolute_uri(reverse('voting:election_detail', kwargs={'pk': election.pk}))

    if request.method == 'POST':
        send_emails_raw = request.POST.get('send_emails', '')
        send_phones_raw = request.POST.get('send_phones', '')
        emails = _parse_bulk_emails(send_emails_raw)
        phones = _parse_bulk_phones(send_phones_raw)
        if not emails and not phones:
            messages.warning(request, 'Enter at least one email address or phone number.')
        else:
            if getattr(settings, 'DEBUG', False):
                result = send_share_link_to_recipients.apply(
                    kwargs={'share_url': share_url, 'election_title': election.title, 'emails': emails, 'phone_numbers': phones}
                )
            else:
                send_share_link_to_recipients.delay(share_url, election.title, emails=emails, phone_numbers=phones)
                result = None
            if result:
                messages.success(
                    request,
                    f'Link sent to {result.get("emails_sent", 0)} email(s) and {result.get("sms_sent", 0)} phone(s).',
                )
            else:
                messages.success(
                    request,
                    f'Link is being sent to {len(emails)} email(s) and {len(phones)} phone(s).',
                )
        return redirect('voting:shareable_link', pk=election.pk)

    qr_code_image = ''
    try:
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(share_url)
        qr.make(fit=True)
        img = qr.make_image()
        buf = BytesIO()
        img.save(buf, format='PNG')
        qr_code_image = base64.b64encode(buf.getvalue()).decode()
    except Exception as e:
        logging.getLogger(__name__).warning('QR code generation failed: %s', e)

    return render(request, 'voting/shareable_link.html', {
        'election': election,
        'share_url': share_url,
        'shareable_link': share_url,
        'qr_code_image': qr_code_image,
    })


def verify_receipt(request, receipt_code=None):
    """Public receipt verification: confirms vote counted, does not reveal selection."""
    result = None
    not_found = False
    code = receipt_code or (request.POST.get('receipt_code', '') if request.method == 'POST' else '')
    code = code.strip().upper()
    if code:
        try:
            receipt = VoteReceipt.objects.select_related(
                'vote__election', 'vote__ballot'
            ).get(receipt_code=code)
            chain_valid = _verify_chain_for_vote(receipt.vote)
            result = {
                'receipt_code': receipt.receipt_code,
                'election_title': receipt.vote.election.title,
                'ballot_title': receipt.vote.ballot.title,
                'cast_at': receipt.vote.cast_at,
                'vote_token_prefix': receipt.vote.vote_token[:8] + '...',
                'chain_valid': chain_valid,
            }
        except VoteReceipt.DoesNotExist:
            not_found = True
    return render(request, 'voting/verify_receipt.html', {
        'result': result,
        'not_found': not_found,
        'receipt_code_input': receipt_code or code,
    })


def _verify_chain_for_vote(vote):
    try:
        entry = vote.chain_entry
        if entry.sequence_number == 1:
            return True
        prev = VoteChainEntry.objects.get(
            ballot=vote.ballot, sequence_number=entry.sequence_number - 1
        )
        return entry.previous_hash == prev.current_hash
    except Exception:
        return False


@login_required
@require_not_voter
def invite_voters(request, pk):
    """CSV upload and manual email entry for EligibleVoter list. Sends email and SMS (if phone on account) to each new invitee."""
    election = get_object_or_404(Election, pk=pk)
    if not can_manage_election(election, request.user):
        messages.error(request, 'Access denied.')
        return redirect('voting:dashboard')
    if request.method == 'POST':
        emails_added = 0
        emails_skipped = 0
        csv_file = request.FILES.get('csv_file')
        if csv_file:
            content = csv_file.read().decode('utf-8')
            reader = csv.reader(io.StringIO(content))
            for row in reader:
                if row:
                    email = row[0].strip().lower()
                    ev, created = EligibleVoter.objects.get_or_create(
                        election=election, email=email
                    )
                    if created:
                        emails_added += 1
                        invite_url = request.build_absolute_uri(
                            reverse('voting:vote_by_invite', kwargs={'invite_token': ev.invite_token})
                        )
                        if getattr(settings, 'DEBUG', False):
                            send_voter_invite_notification.apply(kwargs={'eligible_voter_id': str(ev.pk), 'invite_url': invite_url})
                        else:
                            send_voter_invite_notification.delay(str(ev.pk), invite_url)
                    else:
                        emails_skipped += 1
        manual_emails = request.POST.get('manual_emails', '')
        for email in [e.strip().lower() for e in manual_emails.splitlines() if e.strip()]:
            ev, created = EligibleVoter.objects.get_or_create(
                election=election, email=email
            )
            if created:
                emails_added += 1
                invite_url = request.build_absolute_uri(
                    reverse('voting:vote_by_invite', kwargs={'invite_token': ev.invite_token})
                )
                if getattr(settings, 'DEBUG', False):
                    send_voter_invite_notification.apply(kwargs={'eligible_voter_id': str(ev.pk), 'invite_url': invite_url})
                else:
                    send_voter_invite_notification.delay(str(ev.pk), invite_url)
            else:
                emails_skipped += 1
        messages.success(
            request,
            f'Added {emails_added} voters. Invites sent by email (and by text when they have a phone on file). {emails_skipped} already on the list.',
        )
        return redirect('voting:invite_voters', pk=election.pk)
    eligible_voters = election.eligible_voters.all().order_by('email')
    return render(request, 'voting/invite_voters.html', {
        'election': election,
        'eligible_voters': eligible_voters,
        'eligible_count': eligible_voters.count(),
    })

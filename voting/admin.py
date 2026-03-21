from django.contrib import admin
from django.db.models import Max
from .models import (
    Election, Ballot, Candidate, Vote, VoteReceipt, ElectionResult,
    EligibleVoter, VotingSession, VoteChainEntry,
)


@admin.register(Election)
class ElectionAdmin(admin.ModelAdmin):
    list_display = ['title', 'election_type', 'status', 'tenant', 'start_date', 'end_date', 'creator']
    list_filter = ['election_type', 'status', 'tenant', 'creator']
    search_fields = ['title', 'description']
    date_hierarchy = 'start_date'


@admin.register(Ballot)
class BallotAdmin(admin.ModelAdmin):
    list_display = ['title', 'election', 'order', 'max_selections', 'is_required']
    list_filter = ['election', 'is_required']
    search_fields = ['title', 'question']

    def save_model(self, request, obj, form, change):
        if not change and obj.election_id:
            last_order = Ballot.objects.filter(election_id=obj.election_id).aggregate(Max('order'))['order__max']
            obj.order = (last_order or -1) + 1
        super().save_model(request, obj, form, change)


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ['name', 'ballot', 'party', 'order', 'is_write_in']
    list_filter = ['ballot', 'party', 'is_write_in']
    search_fields = ['name', 'description']


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ['id', 'election', 'ballot', 'voter', 'cast_at', 'is_verified']
    list_filter = ['election', 'is_verified']
    search_fields = ['voter__email', 'vote_token']
    date_hierarchy = 'cast_at'
    readonly_fields = [
        'encrypted_selections', 'selection_hash', 'verification_hash',
        'vote_token', 'ip_address', 'user_agent', 'cast_at',
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return getattr(request.user, 'role', None) == 'super_admin'

    def delete_model(self, request, obj):
        from userauth.models import SecurityLog
        SecurityLog.objects.create(
            user=request.user,
            action_type='admin_action',
            description=f'Vote {obj.pk} deleted by super_admin {request.user.email}',
            ip_address=request.META.get('REMOTE_ADDR'),
            success=True,
        )
        super().delete_model(request, obj)


@admin.register(VoteReceipt)
class VoteReceiptAdmin(admin.ModelAdmin):
    list_display = ['receipt_code', 'vote', 'generated_at']
    search_fields = ['receipt_code']
    readonly_fields = ['receipt_code', 'generated_at']


@admin.register(ElectionResult)
class ElectionResultAdmin(admin.ModelAdmin):
    list_display = ['election', 'total_votes', 'total_voters', 'published_at', 'sealed_at', 'is_final']
    list_filter = ['is_final', 'published_at']
    readonly_fields = ['encrypted_results', 'results_hash', 'sealed_at', 'public_verification_hash']


@admin.register(EligibleVoter)
class EligibleVoterAdmin(admin.ModelAdmin):
    list_display = ['email', 'election', 'has_voted', 'invited_at']
    list_filter = ['election', 'has_voted']
    search_fields = ['email']


@admin.register(VotingSession)
class VotingSessionAdmin(admin.ModelAdmin):
    list_display = ['user', 'election', 'started_at', 'completed']
    list_filter = ['election', 'completed']


@admin.register(VoteChainEntry)
class VoteChainEntryAdmin(admin.ModelAdmin):
    list_display = ['ballot', 'sequence_number', 'created_at']
    list_filter = ['ballot']


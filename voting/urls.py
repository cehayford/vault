from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    dashboard, election_list, create_election, election_detail, edit_election,
    add_ballot, delete_ballot, vote_ballot, ballot_results, election_results, admin_dashboard,
    user_list, user_detail, user_change_role,
    audit_logs, my_votes, candidate_list, create_candidate, candidate_detail,
    shareable_link, vote_by_invite, verify_receipt, invite_voters,
    export_election_results_csv, export_election_results_pdf,
    create_organisation, org_dashboard, status_view,
    delete_election, election_status_change,
)
from .views_api import ElectionViewSet

app_name = 'voting'

urlpatterns = [
    path('', dashboard, name='dashboard'),
    path('status/', status_view, name='status'),
    path('elections/', election_list, name='election_list'),
    path('elections/create/', create_election, name='create_election'),
    path('elections/<uuid:pk>/', election_detail, name='election_detail'),
    path('elections/<uuid:pk>/edit/', edit_election, name='edit_election'),
    path('elections/<uuid:pk>/delete/', delete_election, name='delete_election'),
    path('elections/<uuid:pk>/status-change/', election_status_change, name='election_status_change'),
    path('elections/<uuid:pk>/share/', shareable_link, name='shareable_link'),
    path('elections/<uuid:pk>/invite-voters/', invite_voters, name='invite_voters'),
    path('elections/<uuid:election_id>/add-ballot/', add_ballot, name='add_ballot'),
    path('ballots/<uuid:pk>/delete/', delete_ballot, name='delete_ballot'),
    path('ballots/<uuid:pk>/vote/', vote_ballot, name='vote_ballot'),
    path('ballots/<uuid:pk>/results/', ballot_results, name='ballot_results'),
    path('elections/<uuid:pk>/results/', election_results, name='election_results'),
    path('elections/<uuid:pk>/results/export/csv/', export_election_results_csv, name='export_election_results_csv'),
    path('elections/<uuid:pk>/results/export/pdf/', export_election_results_pdf, name='export_election_results_pdf'),
    path('admin/', admin_dashboard, name='admin_dashboard'),
    path('users/', user_list, name='user_list'),
    path('users/<int:pk>/', user_detail, name='user_detail'),
    path('users/<int:pk>/change-role/', user_change_role, name='user_change_role'),
    path('audit-logs/', audit_logs, name='audit_logs'),
    path('my-votes/', my_votes, name='my_votes'),
    path('candidates/', candidate_list, name='candidate_list'),
    path('candidates/create/', create_candidate, name='create_candidate'),
    path('candidates/<uuid:pk>/', candidate_detail, name='candidate_detail'),
    path('verify-receipt/', verify_receipt, name='verify_receipt'),
    path('verify-receipt/<str:receipt_code>/', verify_receipt, name='verify_receipt_code'),
    path('vote-by-invite/<str:invite_token>/', vote_by_invite, name='vote_by_invite'),
    # Organisation management (core OrgAdmin)
    path('organisations/create/', create_organisation, name='create_organisation'),
    path('organisations/<slug:org_slug>/', org_dashboard, name='org_dashboard'),
]

router = DefaultRouter()
router.register(r'elections', ElectionViewSet, basename='api-election')
urlpatterns += [path('api/v1/', include(router.urls))]    

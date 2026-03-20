"""Legacy nominee app — stub views only. All work in voting/ and userauth/."""
from django.shortcuts import redirect


def nominee_view(request, headline_id):
    return redirect('voting:dashboard')


def vote_success(request):
    return redirect('voting:dashboard')


def nominee_logs(request, headline_id):
    return redirect('voting:dashboard')


def google_oauth_vote(request, headline_id):
    return redirect('voting:dashboard')

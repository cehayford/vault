from functools import wraps

from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages


def require_role(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            user = request.user
            if not user.is_authenticated:
                return redirect('userauth:login')
            if getattr(user, 'role', None) not in roles:
                from userauth.models import SecurityLog
                SecurityLog.objects.create(
                    user=user,
                    action_type='vote_eligibility_denied',
                    description=f'Role check failed: {user.role} not in {roles} for {request.path}',
                    ip_address=request.META.get('REMOTE_ADDR'),
                    success=False,
                )
                messages.error(request, 'You do not have permission to access this page.')
                return redirect('voting:dashboard')
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


def require_not_voter(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('userauth:login')
        if getattr(request.user, 'role', None) == 'voter':
            messages.error(request, 'Voters cannot perform this action. You can only update your profile and vote.')
            return redirect('voting:dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped


def require_org_membership():
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            user = request.user
            if not user.is_authenticated:
                return redirect('userauth:login')
            if getattr(user, 'role', None) == 'super_admin':
                return view_func(request, *args, **kwargs)
            from voting.models import Organisation
            slug = kwargs.get('org_slug')
            if slug:
                org = get_object_or_404(Organisation, slug=slug)
                if not org.memberships.filter(user=user, is_active=True).exists():
                    messages.error(request, 'You are not a member of this organisation.')
                    return redirect('voting:dashboard')
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


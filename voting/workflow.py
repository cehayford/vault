"""
Election workflow: state machine and validation.

Single source of truth for allowed status transitions and DAG-style rules.
Aligned with Workflow Orchestration & Engineering Standards (Definition Flow).
"""

# Allowed next status per current status (immutable once defined for consistency)
ELECTION_STATUS_TRANSITIONS = {
    'draft': ('scheduled', 'cancelled'),
    'scheduled': ('active', 'cancelled'),
    'active': ('closed', 'cancelled'),
    'closed': ('completed',),
    'completed': (),
    'cancelled': (),
}


def can_transition_election_status(current_status, next_status):
    """Return True if transition from current_status to next_status is allowed."""
    allowed = ELECTION_STATUS_TRANSITIONS.get(current_status, ())
    return next_status in allowed


def is_definition_sealed(status):
    """Return True if election definition (ballots/candidates) should be treated as immutable."""
    return status in ('scheduled', 'active', 'closed', 'completed', 'cancelled')

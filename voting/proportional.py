"""
Proportional representation: seat allocation from vote counts.

Uses largest-remainder (Hare quota) to allocate a fixed number of seats
to candidates in proportion to their vote share.
"""


def allocate_seats_largest_remainder(candidate_votes, total_seats):
    if total_seats <= 0:
        return {c: 0 for c in candidate_votes}
    total_votes = sum(candidate_votes.values())
    if total_votes == 0:
        return {c: 0 for c in candidate_votes}
    quota = total_votes / total_seats
    ids = list(candidate_votes.keys())
    seats = {c: 0 for c in ids}
    remainders = {}
    for c in ids:
        v = candidate_votes[c]
        full = int(v // quota)
        seats[c] = full
        remainders[c] = v - full * quota
    assigned = sum(seats.values())
    for _ in range(total_seats - assigned):
        if not remainders:
            break
        c = max(remainders, key=remainders.get)
        seats[c] += 1
        del remainders[c]
    return seats

from django.conf import settings
from django.db import models
from uuid import uuid4
from voting.models import Election, Ballot


class Vote(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='nominee_votes')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    ballot = models.ForeignKey(Ballot, on_delete=models.CASCADE, related_name='nominee_votes', null=True, blank=True)
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name='nominee_votes', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_locked = models.BooleanField(default=False)
    locked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'election', 'ballot'], condition=models.Q(user__isnull=False), name='unique_user_vote_per_ballot'),
            models.UniqueConstraint(fields=['ip_address', 'election', 'ballot'], condition=models.Q(ip_address__isnull=False), name='unique_ip_vote_per_ballot'),
        ]
    
    def __str__(self):
        voter = self.user.username if self.user else f"Anonymous ({self.ip_address})"
        return f"{voter} voted in {self.ballot.title}"
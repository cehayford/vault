from rest_framework import serializers
from .models import Election, Ballot, Candidate


class CandidateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Candidate
        fields = ['id', 'name', 'description', 'party', 'photo', 'order', 'votes_count']
        read_only_fields = fields


class BallotSerializer(serializers.ModelSerializer):
    candidates = CandidateSerializer(many=True, read_only=True)

    class Meta:
        model = Ballot
        fields = ['id', 'title', 'description', 'question', 'max_selections', 'min_selections', 'order', 'candidates']
        read_only_fields = fields


class ElectionListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Election
        fields = ['id', 'title', 'election_type', 'status', 'start_date', 'end_date', 'brand_name', 'primary_color']
        read_only_fields = fields


class ElectionDetailSerializer(serializers.ModelSerializer):
    ballots = BallotSerializer(many=True, read_only=True)

    class Meta:
        model = Election
        fields = [
            'id', 'title', 'description', 'election_type', 'voting_type', 'status',
            'start_date', 'end_date', 'brand_name', 'primary_color',
            'logo', 'header_img', 'ballots', 'created_at',
        ]
        read_only_fields = fields

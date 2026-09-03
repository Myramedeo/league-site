from rest_framework import serializers

class TeamStandingSerializer(serializers.Serializer):
    team = serializers.CharField(source='team.name')
    wins = serializers.IntegerField()
    losses = serializers.IntegerField()
    ties = serializers.IntegerField()
    runs_for = serializers.IntegerField()
    runs_against = serializers.IntegerField()
    win_pct = serializers.FloatField()
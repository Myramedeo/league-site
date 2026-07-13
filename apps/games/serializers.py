from rest_framework import serializers
from .models import Game, GameResult
from teams.serializers import TeamSerializer

class GameResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = GameResult
        fields = ['home_score', 'away_score']

class GameSerializer(serializers.ModelSerializer):
    home_team = TeamSerializer(read_only=True)
    away_team = TeamSerializer(read_only=True)
    result = GameResultSerializer(read_only=True)

    class Meta:
        model = Game
        fields = ['id', 'date', 'home_team', 'away_team', 'result']
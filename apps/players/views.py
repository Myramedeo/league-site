from django.shortcuts import render, get_object_or_404
from .models import Player
from stats.services import player_batting_stats

from rest_framework import viewsets
from .serializers import PlayerSerializer

class PlayerViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Player.objects.all().order_by('last_name', 'first_name')
    serializer_class = PlayerSerializer

def player_detail(request, player_id):
    player = get_object_or_404(Player, id=player_id)
    batting_stats = player_batting_stats(player)

    return render(request, 'players/player_detail.html', {
        'player': player,
        'batting_stats': batting_stats,
    })
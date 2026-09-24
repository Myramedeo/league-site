from django.shortcuts import render, get_object_or_404
from core.utils import get_selected_competition
from .models import Player
from stats.services import player_batting_stats, competition_batting_stats

from rest_framework import viewsets
from .serializers import PlayerSerializer

class PlayerViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Player.objects.all().order_by('last_name', 'first_name')
    serializer_class = PlayerSerializer

def player_list(request):
    from teams.models import Competition

    competition = get_selected_competition(request)
    batting_stats = competition_batting_stats(competition) if competition else []

    return render(request, 'players/player_list.html', {
        'all_competitions': Competition.objects.select_related('season'),
        'competition': competition,
        'batting_stats': batting_stats,
    })

def player_detail(request, player_id):
    player = get_object_or_404(Player, id=player_id)
    batting_stats = player_batting_stats(player)

    return render(request, 'players/player_detail.html', {
        'player': player,
        'batting_stats': batting_stats,
    })
from django.shortcuts import render, get_object_or_404
from django.db.models import Sum
from .models import Player
from stats.models import BattingStatLine

from rest_framework import viewsets
from .serializers import PlayerSerializer

class PlayerViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Player.objects.all().order_by('last_name', 'first_name')
    serializer_class = PlayerSerializer

def player_detail(request, player_id):
    player = get_object_or_404(Player, id=player_id)

    batting_totals = (
        BattingStatLine.objects.filter(player=player)
        .aggregate(at_bats=Sum('at_bats'), hits=Sum('hits'), rbis=Sum('rbis'))
    )
    batting_avg = (
        round(batting_totals['hits'] / batting_totals['at_bats'], 3)
        if batting_totals['at_bats'] else 0.0
    )

    return render(request, 'players/player_detail.html', {
        'player': player,
        'batting_totals': batting_totals,
        'batting_avg': batting_avg,
    })
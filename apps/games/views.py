from django.shortcuts import get_object_or_404, render
from rest_framework import viewsets
from players.models import Roster
from stats.models import BattingStatLine
from .models import Game
from .serializers import GameSerializer

class GameViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Game.objects.select_related('home_team', 'away_team', 'result').order_by('date')
    serializer_class = GameSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        season_id = self.request.query_params.get('season')
        if season_id:
            qs = qs.filter(season_id=season_id)
        return qs


def game_detail(request, game_id):
    game = get_object_or_404(
        Game.objects.select_related('season', 'home_team', 'away_team', 'result'),
        id=game_id,
    )

    batting_lines = list(
        BattingStatLine.objects.filter(game=game).select_related('player').order_by('player__last_name', 'player__first_name')
    )

    roster_by_player = {
        roster.player_id: roster.team_id
        for roster in Roster.objects.filter(player__in=[line.player_id for line in batting_lines], season=game.season)
    }

    def split_lines(lines):
        home_lines = []
        away_lines = []
        for line in lines:
            team_id = roster_by_player.get(line.player_id)
            if team_id == game.home_team_id:
                home_lines.append(line)
            elif team_id == game.away_team_id:
                away_lines.append(line)
        return home_lines, away_lines

    home_batting_lines, away_batting_lines = split_lines(batting_lines)

    home_runs = [int(run) for run in (game.result.home_runs if game.result else [])]
    away_runs = [int(run) for run in (game.result.away_runs if game.result else [])]

    inning_rows = []
    for inning in range(1, 10):
        home_inning = home_runs[inning - 1] if inning <= len(home_runs) else 0
        away_inning = away_runs[inning - 1] if inning <= len(away_runs) else 0
        inning_rows.append((inning, home_inning, away_inning))

    return render(request, 'games/game_detail.html', {
        'game': game,
        'result': game.result,
        'inning_rows': inning_rows,
        'home_batting_lines': home_batting_lines,
        'away_batting_lines': away_batting_lines,
        'inning_count': max(len(home_runs), len(away_runs), 9),
    })
from django.shortcuts import render
from teams.models import Season
from games.services import compute_standings
from stats.services import batting_leaderboard, era_leaderboard
from games.models import Game

from rest_framework.decorators import api_view
from rest_framework.response import Response
from .serializers import TeamStandingSerializer

from django.views.decorators.cache import cache_page

@api_view(['GET'])
def standings_api(request):
    season_year = request.query_params.get('season')
    season = (
        Season.objects.get(year=season_year) if season_year
        else Season.objects.order_by('-year').first()
    )
    if not season:
        return Response([])

    standings = compute_standings(season)
    serializer = TeamStandingSerializer(standings, many=True)
    return Response(serializer.data)

def schedule(request):
    season = Season.objects.order_by('-year').first()
    games = (
        Game.objects.filter(season=season)
        .select_related('home_team', 'away_team', 'result')
        .order_by('date')
    ) if season else []
    return render(request, 'core/schedule.html', {'season': season, 'games': games})

@cache_page(60 * 15)
def leaderboards(request):
    season = Season.objects.order_by('-year').first()
    return render(request, 'core/leaderboards.html', {
        'season': season,
        'batting_leaders': batting_leaderboard(season, min_at_bats=5) if season else [],
        'era_leaders': era_leaderboard(season, min_innings=3) if season else [],
    })

def home(request):
    season = Season.objects.order_by('-year').first()
    standings_list = compute_standings(season) if season else []
    return render(request, 'core/home.html', {
        'season': season,
        'standings': standings_list,
    })

@cache_page(60 * 15)  # 15 minutes
def standings(request):
    season = Season.objects.order_by('-year').first()
    standings_list = compute_standings(season) if season else []
    return render(request, 'core/standings.html', {
        'season': season,
        'standings': standings_list,
    })
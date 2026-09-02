from django.shortcuts import get_object_or_404, render
from teams.models import Season
from games.services import compute_standings
from stats.services import batting_leaderboard
from games.models import Game
from announcements.models import Announcement
from .models import Article
from .utils import get_selected_season

from rest_framework.decorators import api_view
from rest_framework.response import Response
from .serializers import TeamStandingSerializer

from django.views.decorators.cache import cache_page
from django.utils import timezone

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
    season = get_selected_season(request)
    games = (
        Game.objects.filter(season=season)
        .select_related('home_team', 'away_team', 'result')
        .order_by('date')
    ) if season else []
    completed_statuses = ('F', 'W', 'L', 'T', 'FFT', 'PPD')
    upcoming_games = [g for g in games if g.status not in completed_statuses]
    completed_games = sorted(
        (g for g in games if g.status in completed_statuses),
        key=lambda g: g.date,
        reverse=True,
    )
    return render(request, 'core/schedule.html', {
        'season': season,
        'upcoming_games': upcoming_games,
        'completed_games': completed_games,
        'all_seasons': Season.objects.order_by('-year'),
    })

@cache_page(60 * 15)
def leaderboards(request):
    season = get_selected_season(request)
    return render(request, 'core/leaderboards.html', {
        'season': season,
        'batting_leaders': batting_leaderboard(season, min_at_bats=5) if season else [],
        'all_seasons': Season.objects.order_by('-year'),
    })

def home(request):
    season = get_selected_season(request)
    standings_list = compute_standings(season) if season else []
    announcements = Announcement.objects.filter(active=True)
    today = timezone.localdate()
    games = Game.objects.filter(season=season).select_related(
        'home_team', 'away_team', 'result'
    ) if season else Game.objects.none()
    upcoming_games = games.filter(date__gte=today, status='TBP').order_by(
        'date', 'scheduled_time'
    )[:3]
    recent_games = games.filter(
        date__lte=today,
        status__in=('F', 'W', 'L', 'T', 'FFT'),
    ).order_by('-date', '-scheduled_time')[:3]
    return render(request, 'core/home.html', {
        'season': season,
        'standings': standings_list,
        'announcements': announcements,
        'upcoming_games': upcoming_games,
        'recent_games': recent_games,
        'all_seasons': Season.objects.order_by('-year'),
    })

def article_list(request):
    articles = Article.objects.all()
    return render(request, 'core/article_list.html', {
        'articles': articles,
    })

def article_detail(request, slug):
    article = get_object_or_404(Article, slug=slug)
    return render(request, 'core/article.html', {
        'article': article,
    })

@cache_page(60 * 15)  # 15 minutes
def standings(request):
    season = get_selected_season(request)
    standings_list = compute_standings(season) if season else []
    return render(request, 'core/standings.html', {
        'season': season,
        'standings': standings_list,
        'all_seasons': Season.objects.order_by('-year'),
    })
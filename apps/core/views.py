from django.shortcuts import get_object_or_404, render
from teams.models import Competition
from games.services import compute_standings
from stats.services import batting_leaderboard, rbi_leaderboard, runs_leaderboard
from games.models import Game
from announcements.models import Announcement
from .models import Article
from .utils import get_selected_competition

from rest_framework.decorators import api_view
from rest_framework.response import Response
from .serializers import TeamStandingSerializer

from django.views.decorators.cache import cache_page
from django.utils import timezone

@api_view(['GET'])
def standings_api(request):
    competition_id = request.query_params.get('competition')
    competition = (
        Competition.objects.filter(id=competition_id).first() if competition_id
        else Competition.objects.order_by('-id').first()
    )
    if not competition:
        return Response([])

    standings = compute_standings(competition)
    serializer = TeamStandingSerializer(standings, many=True)
    return Response(serializer.data)

def schedule(request):
    competition = get_selected_competition(request)
    games = (
        Game.objects.filter(competition=competition)
        .select_related('home_team', 'away_team', 'result')
        .order_by('date')
    ) if competition else []
    completed_statuses = ('F', 'W', 'L', 'T', 'FFT', 'PPD', 'CAN')
    upcoming_games = [g for g in games if g.status not in completed_statuses]
    completed_games = sorted(
        (g for g in games if g.status in completed_statuses),
        key=lambda g: g.date,
        reverse=True,
    )
    return render(request, 'core/schedule.html', {
        'competition': competition,
        'upcoming_games': upcoming_games,
        'completed_games': completed_games,
        'all_competitions': Competition.objects.select_related('season'),
    })

@cache_page(60 * 15)
def leaderboards(request):
    competition = get_selected_competition(request)
    return render(request, 'core/leaderboards.html', {
        'competition': competition,
        'batting_leaders': batting_leaderboard(competition, min_at_bats=5) if competition else [],
        'rbi_leaders': rbi_leaderboard(competition) if competition else [],
        'runs_leaders': runs_leaderboard(competition) if competition else [],
        'all_competitions': Competition.objects.select_related('season'),
    })

def home(request):
    competition = get_selected_competition(request)
    standings_list = compute_standings(competition) if competition else []
    announcements = Announcement.objects.filter(active=True)
    today = timezone.localdate()
    games = Game.objects.filter(competition=competition).select_related(
        'home_team', 'away_team', 'result'
    ) if competition else Game.objects.none()
    upcoming_games = games.filter(date__gte=today, status='TBP').order_by(
        'date', 'scheduled_time'
    )[:3]
    recent_games = games.filter(
        date__lte=today,
        status__in=('F', 'W', 'L', 'T', 'FFT'),
    ).order_by('-date', '-scheduled_time')[:3]
    return render(request, 'core/home.html', {
        'competition': competition,
        'standings': standings_list,
        'announcements': announcements,
        'upcoming_games': upcoming_games,
        'recent_games': recent_games,
        'all_competitions': Competition.objects.select_related('season'),
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
    competition = get_selected_competition(request)
    standings_list = compute_standings(competition) if competition else []
    return render(request, 'core/standings.html', {
        'competition': competition,
        'standings': standings_list,
        'all_competitions': Competition.objects.select_related('season'),
    })
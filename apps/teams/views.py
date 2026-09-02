from django.shortcuts import render, get_object_or_404
from core.utils import get_selected_season
from .models import Team, Season

from rest_framework import viewsets
from .serializers import TeamSerializer, SeasonSerializer

class TeamViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Team.objects.all().order_by('name')
    serializer_class = TeamSerializer

class SeasonViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Season.objects.all().order_by('-year')
    serializer_class = SeasonSerializer

def team_list(request):
    season = get_selected_season(request)
    teams = (
        Team.objects.filter(seasons=season).order_by('name').distinct()
        if season else Team.objects.none()
    )
    return render(request, 'teams/team_list.html', {
        'all_seasons': Season.objects.order_by('-year'),
        'season': season,
        'teams': teams,
    })

def team_detail(request, team_id):
    team = get_object_or_404(Team, id=team_id)
    # current season's roster
    roster = team.roster_set.select_related('player', 'season').order_by('-season__year')
    return render(request, 'teams/team_detail.html', {'team': team, 'roster': roster})
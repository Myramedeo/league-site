from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, render

from games.models import Game
from teams.models import Season


@staff_member_required
def portal(request):
	season = Season.objects.order_by('-year').first()
	games = (
		Game.objects.filter(season=season)
		.select_related('season', 'home_team', 'away_team', 'result')
		.order_by('date', 'scheduled_time', 'id')
	) if season else []

	return render(request, 'game_entry/portal.html', {
		'season': season,
		'games': games,
	})


@staff_member_required
def game_workspace(request, game_id):
	game = get_object_or_404(
		Game.objects.select_related('season', 'home_team', 'away_team', 'result'),
		id=game_id,
	)

	return render(request, 'game_entry/game_workspace.html', {
		'game': game,
	})

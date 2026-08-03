from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login
from django.contrib.auth.forms import AuthenticationForm
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from games.models import Game
from players.models import Player, Roster
from teams.models import Season

from .forms import GameStateForm, LineupSubstitutionForm, TeamLineupForm
from .models import LineupSpot, LineupSubstitution, PlateAppearance, ScoringSession, TeamLineup


def staff_sign_in(request):
	next_url = _safe_next_url(request, default=reverse('game_entry:portal'))

	if request.user.is_authenticated and request.user.is_staff:
		return redirect(next_url)

	form = AuthenticationForm(request, data=request.POST or None)
	if request.method == 'POST' and form.is_valid():
		user = form.get_user()
		if not user.is_staff:
			form.add_error(None, 'This account does not have staff access for game entry.')
		else:
			login(request, user)
			messages.success(request, 'Signed in. You can now access game entry tools.')
			return redirect(next_url)

	return render(request, 'game_entry/sign_in.html', {
		'form': form,
		'next': next_url,
	})


@staff_member_required(login_url='game_entry:sign_in')
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


@staff_member_required(login_url='game_entry:sign_in')
def game_workspace(request, game_id):
	game = get_object_or_404(
		Game.objects.select_related('season', 'home_team', 'away_team', 'result'),
		id=game_id,
	)
	session, _ = ScoringSession.objects.get_or_create(
		game=game,
		defaults={'started_by': request.user},
	)

	away_roster = _roster_for_team(game, game.away_team_id)
	home_roster = _roster_for_team(game, game.home_team_id)

	away_lineup = _get_team_lineup(session, game.away_team_id)
	home_lineup = _get_team_lineup(session, game.home_team_id)
	lineup_ready = away_lineup is not None and away_lineup.spots.exists() and home_lineup is not None and home_lineup.spots.exists()
	all_roster_players = _combined_roster_for_game(game)
	away_form = None
	home_form = None
	away_substitution_form = LineupSubstitutionForm(
		prefix='away_sub',
		lineup=away_lineup,
		roster_queryset=away_roster,
	)
	home_substitution_form = LineupSubstitutionForm(
		prefix='home_sub',
		lineup=home_lineup,
		roster_queryset=home_roster,
	)
	state_form = GameStateForm(
		prefix='state',
		player_queryset=all_roster_players,
		initial={
			'current_inning': session.current_inning,
			'half_inning': session.half_inning,
			'outs': session.outs,
			'first_base_runner': session.first_base_runner,
			'second_base_runner': session.second_base_runner,
			'third_base_runner': session.third_base_runner,
		},
	)

	if request.method == 'POST':
		action = request.POST.get('action')
		if action == 'save_lineups':
			if session.has_started:
				messages.error(request, 'Lineups are locked after scoring starts. Use substitutions to make changes.')
				return HttpResponseRedirect(reverse('game_entry:game_workspace', args=[game.id]))

			away_form = TeamLineupForm(
				request.POST,
				prefix='away',
				roster_queryset=away_roster,
				team_label=f'{game.away_team} batting order',
				initial_players=_lineup_players(away_lineup),
			)
			home_form = TeamLineupForm(
				request.POST,
				prefix='home',
				roster_queryset=home_roster,
				team_label=f'{game.home_team} batting order',
				initial_players=_lineup_players(home_lineup),
			)

			if away_form.is_valid() and home_form.is_valid():
				with transaction.atomic():
					away_lineup = _save_lineup(session, game.away_team_id, away_form.cleaned_data['ordered_players'])
					home_lineup = _save_lineup(session, game.home_team_id, home_form.cleaned_data['ordered_players'])
					session.lineups_locked = False
					session.save(update_fields=['lineups_locked', 'updated_at'])
					lineup_ready = True
				messages.success(request, 'Lineups saved. You can start scoring now.')
				return HttpResponseRedirect(reverse('game_entry:game_workspace', args=[game.id]))

			messages.error(request, 'Fix lineup errors before starting scoring.')
		elif action == 'update_game_state':
			state_form = GameStateForm(
				request.POST,
				prefix='state',
				player_queryset=all_roster_players,
			)
			if state_form.is_valid():
				session.current_inning = state_form.cleaned_data['current_inning']
				session.half_inning = state_form.cleaned_data['half_inning']
				session.outs = state_form.cleaned_data['outs']
				session.first_base_runner = state_form.cleaned_data['first_base_runner']
				session.second_base_runner = state_form.cleaned_data['second_base_runner']
				session.third_base_runner = state_form.cleaned_data['third_base_runner']
				session.save(update_fields=[
					'current_inning',
					'half_inning',
					'outs',
					'first_base_runner',
					'second_base_runner',
					'third_base_runner',
					'updated_at',
				])
				messages.success(request, 'Game state updated.')
				return HttpResponseRedirect(reverse('game_entry:game_workspace', args=[game.id]))
			messages.error(request, 'Fix game state errors before saving.')
		elif action in ('substitute_away', 'substitute_home'):
			if action == 'substitute_away':
				target_lineup = away_lineup
				target_roster = away_roster
				form_prefix = 'away_sub'
				target_team = game.away_team
			else:
				target_lineup = home_lineup
				target_roster = home_roster
				form_prefix = 'home_sub'
				target_team = game.home_team

			if not target_lineup or not target_lineup.spots.exists():
				messages.error(request, 'Save lineups before recording substitutions.')
				return HttpResponseRedirect(reverse('game_entry:game_workspace', args=[game.id]))

			sub_form = LineupSubstitutionForm(
				request.POST,
				prefix=form_prefix,
				lineup=target_lineup,
				roster_queryset=target_roster,
			)
			if action == 'substitute_away':
				away_substitution_form = sub_form
			else:
				home_substitution_form = sub_form

			if sub_form.is_valid():
				spot = sub_form.cleaned_data['spot']
				outgoing_player = sub_form.cleaned_data['outgoing_player']
				incoming_player = sub_form.cleaned_data['incoming_player']
				spot.player = incoming_player
				spot.save(update_fields=['player'])

				LineupSubstitution.objects.create(
					session=session,
					lineup=target_lineup,
					team=target_team,
					batting_order=spot.batting_order,
					outgoing_player=outgoing_player,
					incoming_player=incoming_player,
					notes=sub_form.cleaned_data.get('notes', ''),
					recorded_by=request.user,
				)
				messages.success(
					request,
					f'Substitution saved: {outgoing_player} -> {incoming_player} at spot {spot.batting_order}.',
				)
				return HttpResponseRedirect(reverse('game_entry:game_workspace', args=[game.id]))

			messages.error(request, 'Fix substitution errors before saving.')
		elif action == 'record_plate_appearance':
			team_key = request.POST.get('offense_team')
			result = request.POST.get('result', 'OTHER')
			notes = request.POST.get('notes', '').strip()
			valid_results = {choice[0] for choice in PlateAppearance.RESULT_CHOICES}
			if result not in valid_results:
				result = 'OTHER'

			if team_key == 'away':
				target_lineup = away_lineup
			elif team_key == 'home':
				target_lineup = home_lineup
			else:
				target_lineup = None

			if not target_lineup or not target_lineup.spots.exists():
				messages.error(request, 'Set and save both lineups before recording plate appearances.')
				return HttpResponseRedirect(reverse('game_entry:game_workspace', args=[game.id]))

			batter = target_lineup.current_batter
			if not batter:
				messages.error(request, 'This lineup has no current batter. Save lineups first.')
				return HttpResponseRedirect(reverse('game_entry:game_workspace', args=[game.id]))

			PlateAppearance.objects.create(
				session=session,
				lineup=target_lineup,
				offense_team=target_lineup.team,
				batter=batter,
				inning_number=session.current_inning,
				half_inning=session.half_inning,
				outs_before=session.outs,
				first_base_runner_before=session.first_base_runner,
				second_base_runner_before=session.second_base_runner,
				third_base_runner_before=session.third_base_runner,
				result=result,
				notes=notes,
				recorded_by=request.user,
			)
			session.start_scoring()
			target_lineup.advance_batter()
			messages.success(request, f'Recorded {result} for {batter}.')
			return HttpResponseRedirect(reverse('game_entry:game_workspace', args=[game.id]))

	if away_form is None or home_form is None:
		away_form = TeamLineupForm(
			prefix='away',
			roster_queryset=away_roster,
			team_label=f'{game.away_team} batting order',
			initial_players=_lineup_players(away_lineup),
		)
		home_form = TeamLineupForm(
			prefix='home',
			roster_queryset=home_roster,
			team_label=f'{game.home_team} batting order',
			initial_players=_lineup_players(home_lineup),
		)

	plate_appearances = session.plate_appearances.select_related('batter', 'offense_team').all()[:15]

	return render(request, 'game_entry/game_workspace.html', {
		'game': game,
		'session': session,
		'away_form': away_form,
		'home_form': home_form,
		'away_lineup': away_lineup,
		'home_lineup': home_lineup,
		'away_substitution_form': away_substitution_form,
		'home_substitution_form': home_substitution_form,
		'state_form': state_form,
		'lineup_ready': lineup_ready,
		'plate_appearances': plate_appearances,
	})


def _roster_for_team(game, team_id):
	roster_player_ids = Roster.objects.filter(
		season=game.season,
		team_id=team_id,
	).values_list('player_id', flat=True)
	return Player.objects.filter(id__in=roster_player_ids).order_by('last_name', 'first_name')


def _lineup_players(team_lineup):
	if not team_lineup:
		return []
	return [spot.player for spot in team_lineup.batting_order]


def _combined_roster_for_game(game):
	roster_player_ids = Roster.objects.filter(
		season=game.season,
		team_id__in=[game.home_team_id, game.away_team_id],
	).values_list('player_id', flat=True)
	return Player.objects.filter(id__in=roster_player_ids).order_by('last_name', 'first_name')


def _get_team_lineup(session, team_id):
	return TeamLineup.objects.filter(session=session, team_id=team_id).prefetch_related('spots__player').first()


def _safe_next_url(request, default):
	next_url = request.POST.get('next') or request.GET.get('next')
	if next_url and url_has_allowed_host_and_scheme(
		url=next_url,
		allowed_hosts={request.get_host()},
		require_https=request.is_secure(),
	):
		return next_url
	return default


def _save_lineup(session, team_id, ordered_players):
	lineup, _ = TeamLineup.objects.get_or_create(session=session, team_id=team_id)
	lineup.spots.all().delete()
	LineupSpot.objects.bulk_create([
		LineupSpot(team_lineup=lineup, player=player, batting_order=index)
		for index, player in enumerate(ordered_players, start=1)
	])
	lineup.batting_index = 0
	lineup.save(update_fields=['batting_index'])
	return lineup

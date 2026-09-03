from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login
from django.contrib.auth.forms import AuthenticationForm
from django.db import transaction
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
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
	completed_statuses = ('F', 'W', 'L', 'T', 'FFT', 'PPD')
	upcoming_games = [game for game in games if game.status not in completed_statuses]
	completed_games = sorted(
		(game for game in games if game.status in completed_statuses),
		key=lambda game: (game.date, game.scheduled_time or ''),
		reverse=True,
	)

	return render(request, 'game_entry/portal.html', {
		'season': season,
		'upcoming_games': upcoming_games,
		'completed_games': completed_games,
	})


@staff_member_required(login_url='game_entry:sign_in')
def game_workspace(request, game_id):
	game, session = _get_game_and_session(game_id, request.user)
	context = _build_workspace_render_context(game, session)

	if request.method == 'POST':
		action = request.POST.get('action')
		if action == 'save_lineups':
			result = _save_lineups_action(request, game, session)
			if result['success']:
				messages.success(request, result['message'])
				return HttpResponseRedirect(reverse('game_entry:game_workspace', args=[game.id]))
			messages.error(request, result['message'])
			if result.get('redirect_on_error'):
				return HttpResponseRedirect(reverse('game_entry:game_workspace', args=[game.id]))
			context['away_form'] = result.get('away_form', context['away_form'])
			context['home_form'] = result.get('home_form', context['home_form'])
		elif action == 'update_game_state':
			result = _update_game_state_action(request, game, session)
			if result['success']:
				messages.success(request, result['message'])
				return HttpResponseRedirect(reverse('game_entry:game_workspace', args=[game.id]))
			messages.error(request, result['message'])
			context['state_form'] = result['state_form']
		elif action in ('substitute_away', 'substitute_home'):
			team_key = 'away' if action == 'substitute_away' else 'home'
			result = _substitution_action(request, game, session, team_key)
			if result['success']:
				messages.success(request, result['message'])
				return HttpResponseRedirect(reverse('game_entry:game_workspace', args=[game.id]))
			messages.error(request, result['message'])
			if team_key == 'away' and result.get('sub_form') is not None:
				context['away_substitution_form'] = result['sub_form']
			if team_key == 'home' and result.get('sub_form') is not None:
				context['home_substitution_form'] = result['sub_form']
			if result.get('redirect_on_error'):
				return HttpResponseRedirect(reverse('game_entry:game_workspace', args=[game.id]))
		elif action == 'record_plate_appearance':
			result = _record_plate_appearance_action(request, game, session)
			if result['success']:
				messages.success(request, result['message'])
				return HttpResponseRedirect(reverse('game_entry:game_workspace', args=[game.id]))
			messages.error(request, result['message'])
			if result.get('redirect_on_error', True):
				return HttpResponseRedirect(reverse('game_entry:game_workspace', args=[game.id]))

	return render(request, 'game_entry/game_workspace.html', context)


@staff_member_required(login_url='game_entry:sign_in')
def update_game_state_fragment(request, game_id):
	if request.method != 'POST':
		return redirect('game_entry:game_workspace', game_id=game_id)

	game, session = _get_game_and_session(game_id, request.user)
	result = _update_game_state_action(request, game, session)
	if result['success']:
		return _render_state_fragment_response(
			request,
			game,
			session,
			result['state_form'],
			alert_message=result['message'],
			alert_level='success',
		)
	return _render_state_fragment_response(
		request,
		game,
		session,
		result['state_form'],
		alert_message=result['message'],
		alert_level='error',
	)


@staff_member_required(login_url='game_entry:sign_in')
def record_plate_appearance_fragment(request, game_id):
	if request.method != 'POST':
		return redirect('game_entry:game_workspace', game_id=game_id)

	game, session = _get_game_and_session(game_id, request.user)
	result = _record_plate_appearance_action(request, game, session)
	if result['success'] and result.get('started_now'):
		response = HttpResponse('')
		response['HX-Redirect'] = reverse('game_entry:game_workspace', args=[game.id])
		return response

	away_lineup = _get_team_lineup(session, game.away_team_id)
	home_lineup = _get_team_lineup(session, game.home_team_id)
	return _render_plate_appearance_fragment_response(
		request,
		game,
		session,
		away_lineup,
		home_lineup,
		selected_team=result['selected_team'],
		selected_result=result['selected_result'],
		notes=result['notes'],
		alert_message=result['message'],
		alert_level='success' if result['success'] else 'error',
	)


@staff_member_required(login_url='game_entry:sign_in')
def save_lineups_fragment(request, game_id):
	if request.method != 'POST':
		return redirect('game_entry:game_workspace', game_id=game_id)

	game, session = _get_game_and_session(game_id, request.user)
	result = _save_lineups_action(request, game, session)
	updated_context = _build_workspace_render_context(
		game,
		session,
		away_form=result.get('away_form'),
		home_form=result.get('home_form'),
	)
	return _render_lineup_fragment_response(
		request,
		updated_context,
		alert_message=result['message'],
		alert_level='success' if result['success'] else 'error',
	)


@staff_member_required(login_url='game_entry:sign_in')
def substitution_fragment(request, game_id, team_key):
	if request.method != 'POST':
		return redirect('game_entry:game_workspace', game_id=game_id)

	if team_key not in ('away', 'home'):
		return redirect('game_entry:game_workspace', game_id=game_id)

	game, session = _get_game_and_session(game_id, request.user)
	result = _substitution_action(request, game, session, team_key)
	if team_key == 'away':
		updated_context = _build_workspace_render_context(game, session, away_substitution_form=result.get('sub_form'))
	else:
		updated_context = _build_workspace_render_context(game, session, home_substitution_form=result.get('sub_form'))
	return _render_substitution_fragment_response(
		request,
		updated_context,
		alert_message=result['message'],
		alert_level='success' if result['success'] else 'error',
	)


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


def _get_game_and_session(game_id, user):
	game = get_object_or_404(
		Game.objects.select_related('season', 'home_team', 'away_team', 'result'),
		id=game_id,
	)
	session, _ = ScoringSession.objects.get_or_create(
		game=game,
		defaults={'started_by': user},
	)
	return game, session


def _save_lineups_action(request, game, session):
	# Shared mutation path for full-page POST and HTMX fragment requests.
	if session.has_started:
		return {
			'success': False,
			'message': 'Lineups are locked after scoring starts. Use substitutions to make changes.',
			'redirect_on_error': True,
		}

	away_roster = _roster_for_team(game, game.away_team_id)
	home_roster = _roster_for_team(game, game.home_team_id)
	away_lineup = _get_team_lineup(session, game.away_team_id)
	home_lineup = _get_team_lineup(session, game.home_team_id)

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
			_save_lineup(session, game.away_team_id, away_form.cleaned_data['ordered_players'])
			_save_lineup(session, game.home_team_id, home_form.cleaned_data['ordered_players'])
			session.lineups_locked = False
			session.save(update_fields=['lineups_locked', 'updated_at'])
		return {
			'success': True,
			'message': 'Lineups saved. You can start scoring now.',
		}

	return {
		'success': False,
		'message': 'Fix lineup errors before starting scoring.',
		'away_form': away_form,
		'home_form': home_form,
	}


def _update_game_state_action(request, game, session):
	# Returns a fresh bound/unbound state form so callers can render directly.
	all_roster_players = _combined_roster_for_game(game)
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
		return {
			'success': True,
			'message': 'Game state updated.',
			'state_form': state_form,
		}

	return {
		'success': False,
		'message': 'Fix game state errors before saving.',
		'state_form': state_form,
	}


def _substitution_action(request, game, session, team_key):
	# Team-agnostic substitution logic keyed by 'away' or 'home'.
	away_lineup = _get_team_lineup(session, game.away_team_id)
	home_lineup = _get_team_lineup(session, game.home_team_id)
	away_roster = _roster_for_team(game, game.away_team_id)
	home_roster = _roster_for_team(game, game.home_team_id)

	if team_key == 'away':
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
		return {
			'success': False,
			'message': 'Save lineups before recording substitutions.',
			'redirect_on_error': True,
		}

	sub_form = LineupSubstitutionForm(
		request.POST,
		prefix=form_prefix,
		lineup=target_lineup,
		roster_queryset=target_roster,
	)

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
		return {
			'success': True,
			'message': f'Substitution saved: {outgoing_player} -> {incoming_player} at spot {spot.batting_order}.',
		}

	return {
		'success': False,
		'message': 'Fix substitution errors before saving.',
		'sub_form': sub_form,
		'redirect_on_error': False,
	}


def _record_plate_appearance_action(request, game, session):
	# Carries enough response metadata for both redirect and fragment callers.
	away_lineup = _get_team_lineup(session, game.away_team_id)
	home_lineup = _get_team_lineup(session, game.home_team_id)

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

	selected_team = team_key if team_key in ('away', 'home') else 'away'

	if not target_lineup or not target_lineup.spots.exists():
		return {
			'success': False,
			'message': 'Set and save both lineups before recording plate appearances.',
			'redirect_on_error': True,
			'selected_team': selected_team,
			'selected_result': result,
			'notes': notes,
		}

	batter = target_lineup.current_batter
	if not batter:
		return {
			'success': False,
			'message': 'This lineup has no current batter. Save lineups first.',
			'redirect_on_error': True,
			'selected_team': selected_team,
			'selected_result': result,
			'notes': notes,
		}

	was_started = session.has_started

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

	return {
		'success': True,
		'message': f'Recorded {result} for {batter}.',
		'started_now': (not was_started and session.has_started),
		'selected_team': selected_team,
		'selected_result': 'OTHER',
		'notes': '',
	}


def _render_state_fragment_response(request, game, session, state_form, alert_message='', alert_level='success'):
	state_html = render_to_string(
		'game_entry/partials/game_state_card.html',
		{
			'game': game,
			'session': session,
			'state_form': state_form,
		},
		request=request,
	)
	alerts_html = render_to_string(
		'game_entry/partials/workspace_alerts.html',
		{
			'message': alert_message,
			'level': alert_level,
		},
		request=request,
	)
	return HttpResponse(f'{state_html}\n{alerts_html}')


def _render_plate_appearance_fragment_response(
	request,
	game,
	session,
	away_lineup,
	home_lineup,
	selected_team,
	selected_result,
	notes,
	alert_message,
	alert_level,
):
	plate_form_html = render_to_string(
		'game_entry/partials/plate_appearance_card.html',
		{
			'game': game,
			'session': session,
			'selected_team': selected_team,
			'selected_result': selected_result,
			'notes': notes,
		},
		request=request,
	)
	recent_pa_html = render_to_string(
		'game_entry/partials/recent_plate_appearances.html',
		{
			'plate_appearances': session.plate_appearances.select_related('batter', 'offense_team').all()[:15],
		},
		request=request,
	)
	away_panel_html = render_to_string(
		'game_entry/partials/batting_order_panel.html',
		{
			'lineup': away_lineup,
			'team_name': game.away_team,
			'panel_id': 'away-batting-order-panel',
		},
		request=request,
	)
	home_panel_html = render_to_string(
		'game_entry/partials/batting_order_panel.html',
		{
			'lineup': home_lineup,
			'team_name': game.home_team,
			'panel_id': 'home-batting-order-panel',
		},
		request=request,
	)
	alerts_html = render_to_string(
		'game_entry/partials/workspace_alerts.html',
		{
			'message': alert_message,
			'level': alert_level,
		},
		request=request,
	)

	return HttpResponse('\n'.join([
		plate_form_html,
		recent_pa_html,
		away_panel_html,
		home_panel_html,
		alerts_html,
	]))


def _build_workspace_render_context(
	game,
	session,
	away_form=None,
	home_form=None,
	away_substitution_form=None,
	home_substitution_form=None,
	state_form=None,
):
	away_roster = _roster_for_team(game, game.away_team_id)
	home_roster = _roster_for_team(game, game.home_team_id)
	away_lineup = _get_team_lineup(session, game.away_team_id)
	home_lineup = _get_team_lineup(session, game.home_team_id)
	lineup_ready = (
		away_lineup is not None and away_lineup.spots.exists()
		and home_lineup is not None and home_lineup.spots.exists()
	)

	if away_form is None:
		away_form = TeamLineupForm(
			prefix='away',
			roster_queryset=away_roster,
			team_label=f'{game.away_team} batting order',
			initial_players=_lineup_players(away_lineup),
		)
	if home_form is None:
		home_form = TeamLineupForm(
			prefix='home',
			roster_queryset=home_roster,
			team_label=f'{game.home_team} batting order',
			initial_players=_lineup_players(home_lineup),
		)

	if away_substitution_form is None:
		away_substitution_form = LineupSubstitutionForm(
			prefix='away_sub',
			lineup=away_lineup,
			roster_queryset=away_roster,
		)
	if home_substitution_form is None:
		home_substitution_form = LineupSubstitutionForm(
			prefix='home_sub',
			lineup=home_lineup,
			roster_queryset=home_roster,
		)

	if state_form is None:
		all_roster_players = _combined_roster_for_game(game)
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

	plate_appearances = session.plate_appearances.select_related('batter', 'offense_team').all()[:15]

	return {
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
	}


def _render_lineup_fragment_response(request, context, alert_message, alert_level):
	lineup_editor_html = render_to_string(
		'game_entry/partials/lineup_editor.html',
		context,
		request=request,
	)
	live_sections_html = render_to_string(
		'game_entry/partials/workspace_live_sections.html',
		context,
		request=request,
	)
	alerts_html = render_to_string(
		'game_entry/partials/workspace_alerts.html',
		{
			'message': alert_message,
			'level': alert_level,
		},
		request=request,
	)
	return HttpResponse('\n'.join([
		lineup_editor_html,
		live_sections_html,
		alerts_html,
	]))


def _render_substitution_fragment_response(request, context, alert_message, alert_level):
	substitution_html = render_to_string(
		'game_entry/partials/substitution_section.html',
		context,
		request=request,
	)
	away_panel_html = render_to_string(
		'game_entry/partials/batting_order_panel.html',
		{
			'lineup': context['away_lineup'],
			'team_name': context['game'].away_team,
			'panel_id': 'away-batting-order-panel',
		},
		request=request,
	)
	home_panel_html = render_to_string(
		'game_entry/partials/batting_order_panel.html',
		{
			'lineup': context['home_lineup'],
			'team_name': context['game'].home_team,
			'panel_id': 'home-batting-order-panel',
		},
		request=request,
	)
	alerts_html = render_to_string(
		'game_entry/partials/workspace_alerts.html',
		{
			'message': alert_message,
			'level': alert_level,
		},
		request=request,
	)
	return HttpResponse('\n'.join([
		substitution_html,
		away_panel_html,
		home_panel_html,
		alerts_html,
	]))

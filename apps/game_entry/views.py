from collections import defaultdict

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login
from django.contrib.auth.forms import AuthenticationForm
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from games.models import Game
from players.models import Player, Roster
from teams.models import Season

from . import services
from .forms import BattingSlotForm, ScorecardEntryForm
from .models import BattingSlot, GameScorecard, ScorecardEntry


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
	game, scorecard = _get_game_and_scorecard(game_id, request.user)
	context = _build_workspace_context(game, scorecard)
	return render(request, 'game_entry/game_workspace.html', context)


@staff_member_required(login_url='game_entry:sign_in')
def lineup_slot(request, game_id, team_key, order):
	game, scorecard = _get_game_and_scorecard(game_id, request.user)
	team = _team_for_key(game, team_key)

	if scorecard.is_finalized:
		return _render_team_section(request, game, scorecard, team_key, 'Unfinalize the game before editing lineups.', 'error')

	roster = _roster_for_team(game, team.id)
	existing = BattingSlot.objects.filter(scorecard=scorecard, team=team, order=order).first()

	if request.method == 'POST':
		form = BattingSlotForm(request.POST, roster_queryset=roster)
		if form.is_valid():
			player = form.cleaned_data['player']
			duplicate = BattingSlot.objects.filter(
				scorecard=scorecard, team=team, player=player,
			).exclude(order=order).exists()
			if duplicate:
				form.add_error('player', 'This player is already in the lineup.')
			else:
				BattingSlot.objects.update_or_create(
					scorecard=scorecard, team=team, order=order,
					defaults={'player': player},
				)
				return _render_team_section(request, game, scorecard, team_key, 'Lineup updated.', 'success')
	else:
		form = BattingSlotForm(
			roster_queryset=roster,
			initial={'player': existing.player_id} if existing else None,
		)

	return render(request, 'game_entry/partials/lineup_slot.html', {
		'game': game, 'team_key': team_key, 'order': order, 'form': form,
	})


@staff_member_required(login_url='game_entry:sign_in')
def add_play(request, game_id, team_key):
	game, scorecard = _get_game_and_scorecard(game_id, request.user)
	team = _team_for_key(game, team_key)

	if scorecard.is_finalized:
		return _render_team_section(request, game, scorecard, team_key, 'Unfinalize the game before recording plays.', 'error')

	if request.method == 'POST':
		slot = services.next_batting_slot(scorecard, team)
		if not slot:
			return _render_team_section(request, game, scorecard, team_key, "Set this team's lineup before recording plays.", 'error')

		inning, half_inning = services.current_inning_for_team(scorecard, team)
		runner_1st, runner_2nd, runner_3rd, _ = services.derive_base_state(scorecard, team, inning, half_inning)
		runners_before = (runner_1st, runner_2nd, runner_3rd)
		form = ScorecardEntryForm(request.POST, runners_before=runners_before)
		if form.is_valid():
			play_index = services.next_play_index(scorecard, team, inning, half_inning)
			ScorecardEntry.objects.create(
				scorecard=scorecard, slot=slot, team=team,
				inning=inning, half_inning=half_inning, play_index=play_index,
				result=form.cleaned_data['result'],
				outs_recorded=form.cleaned_data['outs_recorded'],
				rbi=form.cleaned_data['rbi'],
				batter_ending_base=form.cleaned_data['batter_ending_base'],
				runner_1st_before=runner_1st, runner_1st_ending=form.cleaned_data.get('runner_1st_ending', ''),
				runner_2nd_before=runner_2nd, runner_2nd_ending=form.cleaned_data.get('runner_2nd_ending', ''),
				runner_3rd_before=runner_3rd, runner_3rd_ending=form.cleaned_data.get('runner_3rd_ending', ''),
				notation=form.cleaned_data['notation'],
				notes=form.cleaned_data['notes'],
				recorded_by=request.user,
			)
			return _render_team_section(request, game, scorecard, team_key, f'Recorded {slot.player}.', 'success')

		editor_ctx = {
			'team_key': team_key, 'slot': slot, 'form': form, 'entry': None,
			'inning': inning, 'half_inning': half_inning, 'is_last': False,
			'runners_before': runners_before,
		}
	else:
		editor_ctx = _build_play_editor_context(game, scorecard, team_key, selected_result=request.GET.get('result'))

	return render(request, 'game_entry/partials/play_form.html', {'game': game, **editor_ctx})


@staff_member_required(login_url='game_entry:sign_in')
def edit_play(request, game_id, entry_id):
	game, scorecard = _get_game_and_scorecard(game_id, request.user)
	entry = get_object_or_404(
		ScorecardEntry.objects.select_related('slot__player', 'runner_1st_before', 'runner_2nd_before', 'runner_3rd_before'),
		id=entry_id, scorecard=scorecard,
	)
	team_key = 'away' if entry.team_id == game.away_team_id else 'home'

	if scorecard.is_finalized:
		return _render_team_section(request, game, scorecard, team_key, 'Unfinalize the game before editing plays.', 'error')

	runners_before = (entry.runner_1st_before, entry.runner_2nd_before, entry.runner_3rd_before)

	if request.method == 'POST':
		form = ScorecardEntryForm(request.POST, runners_before=runners_before)
		if form.is_valid():
			entry.result = form.cleaned_data['result']
			entry.outs_recorded = form.cleaned_data['outs_recorded']
			entry.rbi = form.cleaned_data['rbi']
			entry.batter_ending_base = form.cleaned_data['batter_ending_base']
			entry.runner_1st_ending = form.cleaned_data.get('runner_1st_ending', '')
			entry.runner_2nd_ending = form.cleaned_data.get('runner_2nd_ending', '')
			entry.runner_3rd_ending = form.cleaned_data.get('runner_3rd_ending', '')
			entry.notation = form.cleaned_data['notation']
			entry.notes = form.cleaned_data['notes']
			entry.save()
			is_last = services.is_last_play_in_half_inning(entry)
			alert = 'Play updated.' if is_last else 'Play updated. Review later plays in this half-inning for consistency.'
			return _render_team_section(request, game, scorecard, team_key, alert, 'success')

		editor_ctx = {
			'team_key': team_key, 'slot': entry.slot, 'form': form, 'entry': entry,
			'inning': entry.inning, 'half_inning': entry.half_inning,
			'is_last': services.is_last_play_in_half_inning(entry),
			'runners_before': runners_before,
		}
	else:
		editor_ctx = _build_play_editor_context(game, scorecard, team_key, entry=entry)

	return render(request, 'game_entry/partials/play_form.html', {'game': game, **editor_ctx})


@staff_member_required(login_url='game_entry:sign_in')
def delete_play(request, game_id, entry_id):
	if request.method != 'POST':
		return redirect('game_entry:game_workspace', game_id=game_id)

	game, scorecard = _get_game_and_scorecard(game_id, request.user)
	entry = get_object_or_404(ScorecardEntry, id=entry_id, scorecard=scorecard)
	team_key = 'away' if entry.team_id == game.away_team_id else 'home'

	if scorecard.is_finalized:
		return _render_team_section(request, game, scorecard, team_key, 'Unfinalize the game before deleting plays.', 'error')

	if not services.is_last_play_in_half_inning(entry):
		return _render_team_section(request, game, scorecard, team_key, 'Only the most recent play in a half-inning can be deleted.', 'error')

	entry.delete()
	return _render_team_section(request, game, scorecard, team_key, 'Play deleted.', 'success')


@staff_member_required(login_url='game_entry:sign_in')
def add_inning(request, game_id):
	if request.method != 'POST':
		return redirect('game_entry:game_workspace', game_id=game_id)

	game, scorecard = _get_game_and_scorecard(game_id, request.user)
	if scorecard.is_finalized:
		messages.error(request, 'Unfinalize the game before adding innings.')
	else:
		scorecard.add_inning()
	return redirect('game_entry:game_workspace', game_id=game_id)


@staff_member_required(login_url='game_entry:sign_in')
def finalize_game(request, game_id):
	if request.method != 'POST':
		return redirect('game_entry:game_workspace', game_id=game_id)

	game, scorecard = _get_game_and_scorecard(game_id, request.user)
	services.finalize_scorecard(scorecard)
	messages.success(request, 'Game finalized. Score and stats have been saved.')
	return redirect('game_entry:game_workspace', game_id=game_id)


@staff_member_required(login_url='game_entry:sign_in')
def unfinalize_game(request, game_id):
	if request.method != 'POST':
		return redirect('game_entry:game_workspace', game_id=game_id)

	game, scorecard = _get_game_and_scorecard(game_id, request.user)
	services.unfinalize_scorecard(scorecard)
	messages.info(request, 'Game unfinalized. You can edit lineups and plays again.')
	return redirect('game_entry:game_workspace', game_id=game_id)


def _team_for_key(game, team_key):
	if team_key == 'away':
		return game.away_team
	if team_key == 'home':
		return game.home_team
	raise Http404('Invalid team key.')


def _roster_for_team(game, team_id):
	roster_player_ids = Roster.objects.filter(
		season=game.season,
		team_id=team_id,
	).values_list('player_id', flat=True)
	return Player.objects.filter(id__in=roster_player_ids).order_by('last_name', 'first_name')


def _safe_next_url(request, default):
	next_url = request.POST.get('next') or request.GET.get('next')
	if next_url and url_has_allowed_host_and_scheme(
		url=next_url,
		allowed_hosts={request.get_host()},
		require_https=request.is_secure(),
	):
		return next_url
	return default


def _get_game_and_scorecard(game_id, user):
	game = get_object_or_404(
		Game.objects.select_related('season', 'home_team', 'away_team', 'result'),
		id=game_id,
	)
	scorecard, _ = GameScorecard.objects.get_or_create(
		game=game,
		defaults={'created_by': user},
	)
	return game, scorecard


def _build_team_grid(scorecard, team, line_summary):
	slots = list(BattingSlot.objects.filter(scorecard=scorecard, team=team).select_related('player').order_by('order'))
	entries = list(
		ScorecardEntry.objects.filter(scorecard=scorecard, team=team)
		.select_related('slot__player')
		.order_by('inning', 'play_index')
	)
	max_entry_inning = max((entry.inning for entry in entries), default=0)
	innings = list(range(1, max(scorecard.displayed_innings, max_entry_inning) + 1))

	entries_by_slot_inning = defaultdict(list)
	for entry in entries:
		entries_by_slot_inning[(entry.slot_id, entry.inning)].append(entry)

	next_slot = slots[len(entries) % len(slots)] if slots else None

	rows = []
	for slot in slots:
		cells = [
			{'inning': inning, 'plays': entries_by_slot_inning.get((slot.id, inning), [])}
			for inning in innings
		]
		rows.append({'slot': slot, 'cells': cells, 'is_next': next_slot is not None and slot.id == next_slot.id})

	return {
		'team': team,
		'slots': slots,
		'innings': innings,
		'rows': rows,
		'next_slot': next_slot,
		'runs': line_summary['runs'],
		'hits': line_summary['hits'],
		'errors': line_summary['errors'],
		'inning_runs': line_summary['inning_runs'],
	}


def _build_workspace_context(game, scorecard):
	line_summary = services.compute_line_summary(scorecard)
	away_grid = _build_team_grid(scorecard, game.away_team, line_summary['away'])
	home_grid = _build_team_grid(scorecard, game.home_team, line_summary['home'])
	away_editor = _build_play_editor_context(game, scorecard, 'away')
	home_editor = _build_play_editor_context(game, scorecard, 'home')

	return {
		'game': game,
		'scorecard': scorecard,
		'away_roster': _roster_for_team(game, game.away_team_id),
		'home_roster': _roster_for_team(game, game.home_team_id),
		'away_grid': away_grid,
		'home_grid': home_grid,
		'away_editor': away_editor,
		'home_editor': home_editor,
		'lineup_slot_range': range(1, BattingSlot.MAX_ORDER + 1),
	}


def _build_play_editor_context(game, scorecard, team_key, selected_result=None, entry=None):
	team = _team_for_key(game, team_key)

	if entry is not None:
		slot = entry.slot
		inning, half_inning = entry.inning, entry.half_inning
		runners_before = (entry.runner_1st_before, entry.runner_2nd_before, entry.runner_3rd_before)
		initial = {
			'result': entry.result, 'outs_recorded': entry.outs_recorded, 'rbi': entry.rbi,
			'batter_ending_base': entry.batter_ending_base,
			'runner_1st_ending': entry.runner_1st_ending, 'runner_2nd_ending': entry.runner_2nd_ending,
			'runner_3rd_ending': entry.runner_3rd_ending, 'notation': entry.notation, 'notes': entry.notes,
		}
		is_last = services.is_last_play_in_half_inning(entry)
	else:
		slot = services.next_batting_slot(scorecard, team)
		if not slot:
			return {'team_key': team_key, 'slot': None, 'form': None, 'entry': None}
		inning, half_inning = services.current_inning_for_team(scorecard, team)
		runner_1st, runner_2nd, runner_3rd, _ = services.derive_base_state(scorecard, team, inning, half_inning)
		runners_before = (runner_1st, runner_2nd, runner_3rd)
		result = selected_result or 'OUT'
		initial = services.suggest_outcome(result, runners_before)
		initial['result'] = result
		is_last = False

	form = ScorecardEntryForm(initial=initial, runners_before=runners_before)
	return {
		'team_key': team_key, 'slot': slot, 'form': form, 'entry': entry,
		'inning': inning, 'half_inning': half_inning, 'is_last': is_last,
		'runners_before': runners_before,
	}


def _render_team_section(request, game, scorecard, team_key, alert_message='', alert_level='success'):
	context = _build_workspace_context(game, scorecard)
	grid_html = render_to_string('game_entry/partials/scorecard_grid.html', {
		'game': game, 'scorecard': scorecard, 'team_key': team_key,
		'grid': context[f'{team_key}_grid'], 'roster': context[f'{team_key}_roster'],
		'lineup_slot_range': context['lineup_slot_range'],
	}, request=request)
	scoreboard_html = render_to_string('game_entry/partials/scoreboard_summary.html', {
		'game': game, 'away_grid': context['away_grid'], 'home_grid': context['home_grid'],
	}, request=request)
	editor_inner_html = render_to_string(
		'game_entry/partials/play_form.html', {'game': game, **context[f'{team_key}_editor']}, request=request,
	)
	editor_html = f'<div id="{team_key}-play-editor" hx-swap-oob="innerHTML">{editor_inner_html}</div>'
	alerts_html = render_to_string('game_entry/partials/alerts.html', {
		'message': alert_message, 'level': alert_level,
	}, request=request)
	return HttpResponse('\n'.join([grid_html, scoreboard_html, editor_html, alerts_html]))

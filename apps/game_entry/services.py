from django.db import models as django_models
from django.db import transaction

from games.models import GameResult, InningScore
from stats.models import BattingStatLine

from .models import BattingSlot, ScorecardEntry


def next_batting_slot(scorecard, team):
	"""The BattingSlot due up next for `team`, based on how many plate appearances it has had."""
	slots = list(BattingSlot.objects.filter(scorecard=scorecard, team=team).order_by('order'))
	if not slots:
		return None
	played_count = ScorecardEntry.objects.filter(scorecard=scorecard, team=team).count()
	return slots[played_count % len(slots)]


def current_inning_for_team(scorecard, team):
	"""The (inning, half_inning) a new play for `team` should be recorded into."""
	half_inning = 'TOP' if team_id_matches_away(scorecard, team) else 'BOT'
	last_entry = (
		ScorecardEntry.objects.filter(scorecard=scorecard, team=team)
		.order_by('-inning', '-play_index')
		.first()
	)
	if not last_entry:
		return 1, half_inning
	_, _, _, outs = derive_base_state(scorecard, team, last_entry.inning, half_inning)
	if outs >= 3:
		return last_entry.inning + 1, half_inning
	return last_entry.inning, half_inning


def team_id_matches_away(scorecard, team):
	return team.id == scorecard.game.away_team_id


def next_play_index(scorecard, team, inning, half_inning):
	last = (
		ScorecardEntry.objects.filter(
			scorecard=scorecard, team=team, inning=inning, half_inning=half_inning,
		)
		.order_by('-play_index')
		.first()
	)
	return (last.play_index + 1) if last else 1


def derive_base_state(scorecard, team, inning, half_inning):
	"""Runners on base and outs recorded so far in this half-inning, computed from prior plays."""
	entries = (
		ScorecardEntry.objects.filter(
			scorecard=scorecard, team=team, inning=inning, half_inning=half_inning,
		)
		.order_by('play_index')
		.select_related('slot__player', 'runner_1st_before', 'runner_2nd_before', 'runner_3rd_before')
	)
	bases = {'1B': None, '2B': None, '3B': None}
	outs = 0
	for entry in entries:
		outs += entry.outs_recorded
		new_bases = {'1B': None, '2B': None, '3B': None}
		for runner, ending in (
			(entry.runner_1st_before, entry.runner_1st_ending),
			(entry.runner_2nd_before, entry.runner_2nd_ending),
			(entry.runner_3rd_before, entry.runner_3rd_ending),
		):
			if runner and ending in new_bases:
				new_bases[ending] = runner
		if entry.batter_ending_base in new_bases:
			new_bases[entry.batter_ending_base] = entry.slot.player
		bases = new_bases
	return bases['1B'], bases['2B'], bases['3B'], min(outs, 3)


def suggest_outcome(result, runners_before):
	"""Standard baseball advancement defaults for `result`, editable by the scorer before saving."""
	runner_1st, runner_2nd, runner_3rd = runners_before
	suggestion = {
		'outs_recorded': 0,
		'rbi': 0,
		'batter_ending_base': 'OUT',
		'runner_1st_ending': '1B' if runner_1st else '',
		'runner_2nd_ending': '2B' if runner_2nd else '',
		'runner_3rd_ending': '3B' if runner_3rd else '',
	}

	def everyone_scores():
		if runner_1st:
			suggestion['runner_1st_ending'] = 'HOME'
		if runner_2nd:
			suggestion['runner_2nd_ending'] = 'HOME'
		if runner_3rd:
			suggestion['runner_3rd_ending'] = 'HOME'

	if result == 'HR':
		suggestion['batter_ending_base'] = 'HOME'
		everyone_scores()
	elif result == '3B':
		suggestion['batter_ending_base'] = '3B'
		everyone_scores()
	elif result == '2B':
		suggestion['batter_ending_base'] = '2B'
		everyone_scores()
	elif result == '1B':
		suggestion['batter_ending_base'] = '1B'
		if runner_1st:
			suggestion['runner_1st_ending'] = '2B'
		if runner_2nd:
			suggestion['runner_2nd_ending'] = 'HOME'
		if runner_3rd:
			suggestion['runner_3rd_ending'] = 'HOME'
	elif result in ('BB', 'HBP'):
		suggestion['batter_ending_base'] = '1B'
		# Only forced runners advance on a walk/HBP.
		if runner_1st:
			suggestion['runner_1st_ending'] = '2B'
			if runner_2nd:
				suggestion['runner_2nd_ending'] = '3B'
				if runner_3rd:
					suggestion['runner_3rd_ending'] = 'HOME'
	elif result == 'E':
		suggestion['batter_ending_base'] = '1B'
		if runner_1st:
			suggestion['runner_1st_ending'] = '2B'
		if runner_2nd:
			suggestion['runner_2nd_ending'] = '3B'
		if runner_3rd:
			suggestion['runner_3rd_ending'] = 'HOME'
	elif result == 'FC':
		suggestion['batter_ending_base'] = '1B'
		suggestion['outs_recorded'] = 1
		# Assume the lead runner is forced out; the scorer can override which one.
		if runner_1st:
			suggestion['runner_1st_ending'] = 'OUT'
		elif runner_2nd:
			suggestion['runner_2nd_ending'] = 'OUT'
		elif runner_3rd:
			suggestion['runner_3rd_ending'] = 'OUT'
	elif result == 'SAC':
		suggestion['batter_ending_base'] = 'OUT'
		suggestion['outs_recorded'] = 1
		if runner_3rd:
			suggestion['runner_3rd_ending'] = 'HOME'
		elif runner_2nd:
			suggestion['runner_2nd_ending'] = '3B'
		elif runner_1st:
			suggestion['runner_1st_ending'] = '2B'
	elif result == 'DP':
		suggestion['batter_ending_base'] = 'OUT'
		suggestion['outs_recorded'] = 2
	else:  # K, OUT, OTHER
		suggestion['batter_ending_base'] = 'OUT'
		suggestion['outs_recorded'] = 1

	suggestion['rbi'] = sum(
		1
		for field in ('batter_ending_base', 'runner_1st_ending', 'runner_2nd_ending', 'runner_3rd_ending')
		if suggestion[field] == 'HOME'
	)
	return suggestion


def compute_line_summary(scorecard):
	"""Per-team runs/hits/errors and per-inning run totals, for the live scoreboard and finalize()."""
	away_team_id = scorecard.game.away_team_id
	summary = {
		'away': {'runs': 0, 'hits': 0, 'errors': 0, 'inning_runs': {}},
		'home': {'runs': 0, 'hits': 0, 'errors': 0, 'inning_runs': {}},
	}
	entries = scorecard.entries.select_related('runner_1st_before', 'runner_2nd_before', 'runner_3rd_before')
	for entry in entries:
		side = 'away' if entry.team_id == away_team_id else 'home'
		other_side = 'home' if side == 'away' else 'away'

		if entry.result in ScorecardEntry.HIT_RESULTS:
			summary[side]['hits'] += 1
		if entry.result == 'E':
			# An error is charged to the fielding (opposing) team.
			summary[other_side]['errors'] += 1

		runs = sum(
			1
			for ending in (
				entry.batter_ending_base,
				entry.runner_1st_ending,
				entry.runner_2nd_ending,
				entry.runner_3rd_ending,
			)
			if ending == 'HOME'
		)
		if runs:
			summary[side]['runs'] += runs
			summary[side]['inning_runs'][entry.inning] = summary[side]['inning_runs'].get(entry.inning, 0) + runs
	return summary


def compute_batting_totals(scorecard):
	"""Per-player BattingStatLine field values, keyed by player id, aggregated from ScorecardEntry rows."""
	totals = {}

	def totals_for(player):
		return totals.setdefault(player.id, {
			'player': player,
			'at_bats': 0, 'runs': 0, 'hits': 0, 'rbis': 0, 'walks': 0,
			'strikeouts': 0, 'singles': 0, 'doubles': 0, 'triples': 0,
			'home_runs': 0, 'hit_by_pitch': 0, 'sacrifices': 0, 'reached_on_error': 0,
		})

	entries = scorecard.entries.select_related(
		'slot__player', 'runner_1st_before', 'runner_2nd_before', 'runner_3rd_before',
	)
	for entry in entries:
		batter = entry.slot.player
		stats = totals_for(batter)

		if entry.result not in ScorecardEntry.NON_AT_BAT_RESULTS:
			stats['at_bats'] += 1

		if entry.result == 'BB':
			stats['walks'] += 1
		elif entry.result == 'HBP':
			stats['hit_by_pitch'] += 1
		elif entry.result == 'K':
			stats['strikeouts'] += 1
		elif entry.result == 'SAC':
			stats['sacrifices'] += 1
		elif entry.result == 'E':
			stats['reached_on_error'] += 1
		elif entry.result in ScorecardEntry.HIT_RESULTS:
			stats['hits'] += 1
			if entry.result == '1B':
				stats['singles'] += 1
			elif entry.result == '2B':
				stats['doubles'] += 1
			elif entry.result == '3B':
				stats['triples'] += 1
			elif entry.result == 'HR':
				stats['home_runs'] += 1

		stats['rbis'] += entry.rbi

		if entry.batter_ending_base == 'HOME':
			stats['runs'] += 1
		for runner, ending in (
			(entry.runner_1st_before, entry.runner_1st_ending),
			(entry.runner_2nd_before, entry.runner_2nd_ending),
			(entry.runner_3rd_before, entry.runner_3rd_ending),
		):
			if runner and ending == 'HOME':
				totals_for(runner)['runs'] += 1

	return totals


@transaction.atomic
def finalize_scorecard(scorecard):
	"""Aggregate ScorecardEntry rows into GameResult/InningScore/BattingStatLine. Safe to re-run."""
	game = scorecard.game
	line_summary = compute_line_summary(scorecard)
	batting_totals = compute_batting_totals(scorecard)
	max_inning = scorecard.entries.aggregate(django_models.Max('inning'))['inning__max'] or 0

	for stats in batting_totals.values():
		player = stats.pop('player')
		BattingStatLine.objects.update_or_create(player=player, game=game, defaults=stats)

	result, _ = GameResult.objects.get_or_create(game=game)
	result.final_home_score = None
	result.final_away_score = None
	result.home_hits = line_summary['home']['hits']
	result.away_hits = line_summary['away']['hits']
	result.home_errors = line_summary['home']['errors']
	result.away_errors = line_summary['away']['errors']
	result.innings_played = max_inning or None
	result.save()

	result.innings.all().delete()
	for inning in range(1, max_inning + 1):
		InningScore.objects.create(
			result=result,
			inning=inning,
			home_runs=line_summary['home']['inning_runs'].get(inning, 0),
			away_runs=line_summary['away']['inning_runs'].get(inning, 0),
		)

	if game.status not in ('CAN', 'PPD', 'FFT'):
		game.status = 'F'
		game.save(update_fields=['status'])

	scorecard.is_finalized = True
	scorecard.save(update_fields=['is_finalized', 'updated_at'])

	return result


def unfinalize_scorecard(scorecard):
	scorecard.is_finalized = False
	scorecard.save(update_fields=['is_finalized', 'updated_at'])


def is_last_play_in_half_inning(entry):
	"""Only the last play in a half-inning may be deleted, to keep the runner chain consistent."""
	return not ScorecardEntry.objects.filter(
		scorecard_id=entry.scorecard_id,
		team_id=entry.team_id,
		inning=entry.inning,
		half_inning=entry.half_inning,
		play_index__gt=entry.play_index,
	).exists()

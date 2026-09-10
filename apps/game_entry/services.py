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
	outs = outs_recorded_for_half_inning(scorecard, team, last_entry.inning, half_inning)
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


def outs_recorded_for_half_inning(scorecard, team, inning, half_inning):
	"""Total outs recorded so far in this half-inning, capped at 3."""
	total = ScorecardEntry.objects.filter(
		scorecard=scorecard, team=team, inning=inning, half_inning=half_inning,
	).aggregate(total=django_models.Sum('outs_recorded'))['total'] or 0
	return min(total, 3)


def missing_lineup_slots(scorecard, team):
	"""Batting-order gaps: numbers with no player assigned below the highest assigned order."""
	orders = set(
		BattingSlot.objects.filter(scorecard=scorecard, team=team).values_list('order', flat=True)
	)
	if not orders:
		return []
	return [order for order in range(1, max(orders) + 1) if order not in orders]


def suggest_outcome(result):
	"""Default outs for `result`, editable by the scorer before saving. RBI/scored are always manual."""
	suggestion = {'outs_recorded': 0, 'rbi': 0, 'scored': False}

	if result == 'DP':
		suggestion['outs_recorded'] = 2
	elif result in ('FC', 'SAC'):
		suggestion['outs_recorded'] = 1
	elif result in ('1B', '2B', '3B', 'HR', 'BB', 'HBP', 'E', 'SKIP'):
		suggestion['outs_recorded'] = 0
	else:  # K, OUT, OTHER
		suggestion['outs_recorded'] = 1

	return suggestion


def compute_line_summary(scorecard):
	"""Per-team runs/hits/errors and per-inning run totals, for the live scoreboard and finalize()."""
	away_team_id = scorecard.game.away_team_id
	summary = {
		'away': {'runs': 0, 'hits': 0, 'errors': 0, 'inning_runs': {}},
		'home': {'runs': 0, 'hits': 0, 'errors': 0, 'inning_runs': {}},
	}
	entries = scorecard.entries.all()
	for entry in entries:
		side = 'away' if entry.team_id == away_team_id else 'home'
		other_side = 'home' if side == 'away' else 'away'

		if entry.result in ScorecardEntry.HIT_RESULTS:
			summary[side]['hits'] += 1
		if entry.result == 'E':
			# An error is charged to the fielding (opposing) team.
			summary[other_side]['errors'] += 1

		if entry.scored:
			summary[side]['runs'] += 1
			summary[side]['inning_runs'][entry.inning] = summary[side]['inning_runs'].get(entry.inning, 0) + 1
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

	entries = scorecard.entries.select_related('slot__player')
	for entry in entries:
		batter = entry.slot.player
		if entry.result == 'SKIP':
			continue
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
		if entry.scored:
			stats['runs'] += 1

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

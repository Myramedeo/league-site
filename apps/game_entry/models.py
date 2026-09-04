from django.conf import settings
from django.db import models

from games.models import Game
from players.models import Player
from teams.models import Team


class GameScorecard(models.Model):
	DEFAULT_DISPLAYED_INNINGS = 9

	game = models.OneToOneField(Game, on_delete=models.CASCADE, related_name='scorecard')
	displayed_innings = models.PositiveSmallIntegerField(default=DEFAULT_DISPLAYED_INNINGS)
	is_finalized = models.BooleanField(default=False)
	created_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='created_scorecards',
	)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ['-created_at']

	def __str__(self):
		return f"Scorecard: {self.game}"

	def add_inning(self):
		self.displayed_innings += 1
		self.save(update_fields=['displayed_innings', 'updated_at'])


class BattingSlot(models.Model):
	MAX_ORDER = 14

	scorecard = models.ForeignKey(GameScorecard, on_delete=models.CASCADE, related_name='batting_slots')
	team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='scorecard_batting_slots')
	order = models.PositiveSmallIntegerField()
	player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='batting_slots')

	class Meta:
		ordering = ['team_id', 'order']
		unique_together = (
			('scorecard', 'team', 'order'),
			('scorecard', 'team', 'player'),
		)

	def __str__(self):
		return f"{self.team} #{self.order}: {self.player}"


class ScorecardEntry(models.Model):
	HALF_INNING_CHOICES = [
		('TOP', 'Top'),
		('BOT', 'Bottom'),
	]

	RESULT_CHOICES = [
		('1B', '1B'),
		('2B', '2B'),
		('3B', '3B'),
		('HR', 'HR'),
		('BB', 'BB'),
		('K', 'K'),
		('OUT', 'OUT'),
		('DP', 'DP'),
		('HBP', 'HBP'),
		('E', 'E'),
		('FC', 'FC'),
		('SAC', 'SAC'),
		('SKIP', 'N/A'),
		('OTHER', 'OTHER'),
	]

	# Results that count toward a player's hit total.
	HIT_RESULTS = {'1B', '2B', '3B', 'HR'}
	# Results that do not count as an official at-bat.
	NON_AT_BAT_RESULTS = {'BB', 'HBP', 'SAC', 'FC', 'SKIP'}

	# Shared vocabulary for "where did this runner/batter end up on this play?" -
	# reused by batter_ending_base and all three runner_*_ending fields so a single
	# value (e.g. 'HOME') always means the same thing when tallying runs.
	BASE_OUTCOME_CHOICES = [
		('1B', '1st Base'),
		('2B', '2nd Base'),
		('3B', '3rd Base'),
		('HOME', 'Scored'),
		('OUT', 'Out'),
	]

	scorecard = models.ForeignKey(GameScorecard, on_delete=models.CASCADE, related_name='entries')
	slot = models.ForeignKey(BattingSlot, on_delete=models.CASCADE, related_name='entries')
	team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='scorecard_entries')
	inning = models.PositiveSmallIntegerField(default=1)
	half_inning = models.CharField(max_length=3, choices=HALF_INNING_CHOICES, default='TOP')
	# Order of this play within its (scorecard, team, inning, half_inning) group.
	play_index = models.PositiveSmallIntegerField(default=1)

	result = models.CharField(max_length=10, choices=RESULT_CHOICES, default='OTHER')
	outs_recorded = models.PositiveSmallIntegerField(default=0)
	rbi = models.PositiveSmallIntegerField(default=0)
	batter_ending_base = models.CharField(max_length=4, choices=BASE_OUTCOME_CHOICES, default='OUT')

	# Runner state is snapshotted from the prior play in this half-inning when the entry is created.
	runner_1st_before = models.ForeignKey(
		Player, null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
	)
	runner_1st_ending = models.CharField(max_length=4, choices=BASE_OUTCOME_CHOICES, blank=True)
	runner_2nd_before = models.ForeignKey(
		Player, null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
	)
	runner_2nd_ending = models.CharField(max_length=4, choices=BASE_OUTCOME_CHOICES, blank=True)
	runner_3rd_before = models.ForeignKey(
		Player, null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
	)
	runner_3rd_ending = models.CharField(max_length=4, choices=BASE_OUTCOME_CHOICES, blank=True)

	notation = models.CharField(max_length=20, blank=True)
	notes = models.CharField(max_length=255, blank=True)
	recorded_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='recorded_scorecard_entries',
	)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ['team_id', 'inning', 'half_inning', 'play_index']
		unique_together = ('scorecard', 'team', 'inning', 'half_inning', 'play_index')

	def __str__(self):
		return f"{self.slot.player} {self.get_result_display()} (inning {self.inning} {self.half_inning})"

	@property
	def batter(self):
		return self.slot.player

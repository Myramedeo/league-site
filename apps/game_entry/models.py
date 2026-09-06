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
	# Whether this batter crossed home plate, set whenever it actually happens (may be on a later play).
	scored = models.BooleanField(default=False)

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

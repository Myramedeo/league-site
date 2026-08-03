from django.conf import settings
from django.db import models
from django.utils import timezone

from games.models import Game
from players.models import Player
from teams.models import Team


class ScoringSession(models.Model):
	HALF_INNING_CHOICES = [
		('TOP', 'Top'),
		('BOT', 'Bottom'),
	]

	game = models.OneToOneField(Game, on_delete=models.CASCADE, related_name='scoring_session')
	started_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='started_scoring_sessions',
	)
	started_at = models.DateTimeField(null=True, blank=True)
	lineups_locked = models.BooleanField(default=False)
	current_inning = models.PositiveSmallIntegerField(default=1)
	half_inning = models.CharField(max_length=3, choices=HALF_INNING_CHOICES, default='TOP')
	outs = models.PositiveSmallIntegerField(default=0)
	first_base_runner = models.ForeignKey(
		Player,
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
		related_name='sessions_on_first_base',
	)
	second_base_runner = models.ForeignKey(
		Player,
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
		related_name='sessions_on_second_base',
	)
	third_base_runner = models.ForeignKey(
		Player,
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
		related_name='sessions_on_third_base',
	)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ['-created_at']

	def __str__(self):
		return f"Scoring Session: {self.game}"

	@property
	def has_started(self):
		return self.started_at is not None or self.plate_appearances.exists()

	def start_scoring(self):
		if self.started_at:
			return
		self.started_at = timezone.now()
		self.lineups_locked = True
		self.save(update_fields=['started_at', 'lineups_locked', 'updated_at'])


class TeamLineup(models.Model):
	session = models.ForeignKey(ScoringSession, on_delete=models.CASCADE, related_name='team_lineups')
	team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='scoring_lineups')
	batting_index = models.PositiveSmallIntegerField(default=0)

	class Meta:
		unique_together = ('session', 'team')

	def __str__(self):
		return f"{self.team} lineup for {self.session.game}"

	@property
	def batting_order(self):
		return self.spots.select_related('player').order_by('batting_order')

	@property
	def current_batter(self):
		spots = list(self.batting_order)
		if not spots:
			return None
		return spots[self.batting_index % len(spots)].player

	def advance_batter(self):
		lineup_count = self.spots.count()
		if lineup_count == 0:
			return
		self.batting_index = (self.batting_index + 1) % lineup_count
		self.save(update_fields=['batting_index'])


class LineupSpot(models.Model):
	team_lineup = models.ForeignKey(TeamLineup, on_delete=models.CASCADE, related_name='spots')
	player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='lineup_spots')
	batting_order = models.PositiveSmallIntegerField()

	class Meta:
		ordering = ['batting_order']
		unique_together = (
			('team_lineup', 'batting_order'),
			('team_lineup', 'player'),
		)

	def __str__(self):
		return f"{self.team_lineup.team} #{self.batting_order}: {self.player}"


class PlateAppearance(models.Model):
	RESULT_CHOICES = [
		('1B', 'Single'),
		('2B', 'Double'),
		('3B', 'Triple'),
		('HR', 'Home Run'),
		('BB', 'Walk'),
		('K', 'Strikeout'),
		('OUT', 'Out'),
		('HBP', 'Hit By Pitch'),
		('E', 'Reached on Error'),
		('SAC', 'Sacrifice'),
		('OTHER', 'Other'),
	]

	session = models.ForeignKey(ScoringSession, on_delete=models.CASCADE, related_name='plate_appearances')
	lineup = models.ForeignKey(TeamLineup, on_delete=models.CASCADE, related_name='plate_appearances')
	offense_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='plate_appearances')
	batter = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='plate_appearances')
	inning_number = models.PositiveSmallIntegerField(default=1)
	half_inning = models.CharField(max_length=3, choices=ScoringSession.HALF_INNING_CHOICES, default='TOP')
	outs_before = models.PositiveSmallIntegerField(default=0)
	first_base_runner_before = models.ForeignKey(
		Player,
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
		related_name='plate_appearances_first_base_before',
	)
	second_base_runner_before = models.ForeignKey(
		Player,
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
		related_name='plate_appearances_second_base_before',
	)
	third_base_runner_before = models.ForeignKey(
		Player,
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
		related_name='plate_appearances_third_base_before',
	)
	result = models.CharField(max_length=10, choices=RESULT_CHOICES, default='OTHER')
	notes = models.CharField(max_length=255, blank=True)
	recorded_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='recorded_plate_appearances',
	)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-created_at']

	def __str__(self):
		return f"{self.batter} {self.get_result_display()} ({self.offense_team})"


class LineupSubstitution(models.Model):
	session = models.ForeignKey(ScoringSession, on_delete=models.CASCADE, related_name='substitutions')
	lineup = models.ForeignKey(TeamLineup, on_delete=models.CASCADE, related_name='substitutions')
	team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='lineup_substitutions')
	batting_order = models.PositiveSmallIntegerField()
	outgoing_player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='subbed_out_events')
	incoming_player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='subbed_in_events')
	notes = models.CharField(max_length=255, blank=True)
	recorded_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='recorded_substitutions',
	)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-created_at']

	def __str__(self):
		return f"{self.team} spot {self.batting_order}: {self.outgoing_player} -> {self.incoming_player}"

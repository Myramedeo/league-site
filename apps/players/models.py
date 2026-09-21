from django.conf import settings
from django.db import models
from teams.models import Competition, Team, Season

class Player(models.Model):
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    jersey_number = models.PositiveSmallIntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    class Meta:
        ordering = ['last_name', 'first_name']


class Roster(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    season = models.ForeignKey(Season, on_delete=models.CASCADE)
    show_in_team_list = models.BooleanField(default=True)
    competition = models.ForeignKey(
        Competition,
        on_delete=models.CASCADE,
        related_name='rosters',
        null=True,
        blank=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('player', 'team', 'season', 'competition'),
                name='unique_player_team_season_competition',
            ),
        ]

    def __str__(self):
        return f"{self.player} — {self.team} ({self.season})"


class LegacyPlayerIdentity(models.Model):
    legacy_player_id = models.PositiveBigIntegerField(unique=True)
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='legacy_identities')
    source_first_name = models.CharField(max_length=50, blank=True)
    source_last_name = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f'{self.source_first_name} {self.source_last_name} ({self.legacy_player_id})'


class PlayerMergeAudit(models.Model):
    target_player = models.ForeignKey(
        Player,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='merge_targets',
    )
    source_player_id = models.PositiveBigIntegerField()
    target_name = models.CharField(max_length=101)
    source_name = models.CharField(max_length=101)
    before_state = models.JSONField()
    after_state = models.JSONField()
    merged_at = models.DateTimeField(auto_now_add=True)
    undone_at = models.DateTimeField(null=True, blank=True)
    merged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='player_merges',
    )

    class Meta:
        ordering = ['-merged_at']

    @property
    def is_undone(self):
        return self.undone_at is not None

    def __str__(self):
        return f'{self.source_name} into {self.target_name} ({self.merged_at:%Y-%m-%d %H:%M})'
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
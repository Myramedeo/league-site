from django.db import models
from teams.models import Team, Season

class Game(models.Model):
    STATUS_CHOICES = [
        ('F', 'Final'),
        ('TBP', 'To be played'),
        ('W', 'Win'),
        ('L', 'Loss'),
        ('T', 'Tie'),
        ('CAN', 'Canceled'),
        ('PPD', 'Postponed'),
        ('SPD', 'Suspended'),
        ('FFT', 'Forfeit'),
    ]

    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name='games')
    home_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='home_games')
    away_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='away_games')
    date = models.DateField()
    scheduled_time = models.TimeField(blank=True, null=True)
    status = models.CharField(max_length=3, choices=STATUS_CHOICES, default='TBP')
    venue = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        if self.scheduled_time:
            return f"{self.away_team} @ {self.home_team} ({self.date} {self.scheduled_time})"
        return f"{self.away_team} @ {self.home_team} ({self.date})"

    class Meta:
        ordering = ['-date']
    
    def clean(self):
        from django.core.exceptions import ValidationError
        if self.home_team_id == self.away_team_id:
            raise ValidationError("Home and away team must be different.")


class GameResult(models.Model):
    game = models.OneToOneField(Game, on_delete=models.CASCADE, related_name='result')
    home_runs = models.JSONField(default=list, blank=True)
    away_runs = models.JSONField(default=list, blank=True)
    home_hits = models.PositiveSmallIntegerField(default=0, blank=True, null=True)
    away_hits = models.PositiveSmallIntegerField(default=0, blank=True, null=True)
    home_errors = models.PositiveSmallIntegerField(default=0, blank=True, null=True)
    away_errors = models.PositiveSmallIntegerField(default=0, blank=True, null=True)
    home_score = models.PositiveSmallIntegerField(default=0, blank=True, null=True)
    away_score = models.PositiveSmallIntegerField(default=0, blank=True, null=True)

    def __str__(self):
        return f"{self.game}: {self.away_score}-{self.home_score}"

    def _coerce_runs(self, runs):
        if not runs:
            return []
        return [int(run) for run in runs]

    def _sum_runs(self, runs):
        return sum(self._coerce_runs(runs))

    def _update_scores_from_innings(self):
        home_runs = self._coerce_runs(self.home_runs)
        away_runs = self._coerce_runs(self.away_runs)

        if home_runs or away_runs:
            self.home_score = self._sum_runs(home_runs)
            self.away_score = self._sum_runs(away_runs)

    def save(self, *args, **kwargs):
        self._update_scores_from_innings()
        super().save(*args, **kwargs)

    def clean(self):
        from django.core.exceptions import ValidationError

        home_runs = self._coerce_runs(self.home_runs)
        away_runs = self._coerce_runs(self.away_runs)

        if len(home_runs) > 9 or len(away_runs) > 9:
            raise ValidationError("Runs can only be recorded for up to 9 innings.")

    @property
    def winner(self):
        if self.home_score > self.away_score:
            return self.game.home_team
        elif self.away_score > self.home_score:
            return self.game.away_team
        return None  # tie
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
    home_score = models.PositiveSmallIntegerField()
    away_score = models.PositiveSmallIntegerField()

    def __str__(self):
        return f"{self.game}: {self.away_score}-{self.home_score}"

    @property
    def winner(self):
        if self.home_score > self.away_score:
            return self.game.home_team
        elif self.away_score > self.home_score:
            return self.game.away_team
        return None  # tie
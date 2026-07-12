from django.db import models
from players.models import Player
from games.models import Game

class BattingStatLine(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='batting_lines')
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='batting_lines')

    at_bats = models.PositiveSmallIntegerField(default=0)
    hits = models.PositiveSmallIntegerField(default=0)
    walks = models.PositiveSmallIntegerField(default=0)
    runs = models.PositiveSmallIntegerField(default=0)
    rbis = models.PositiveSmallIntegerField(default=0)
    strikeouts = models.PositiveSmallIntegerField(default=0)

    class Meta:
        unique_together = ('player', 'game')

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.hits > self.at_bats:
            raise ValidationError("Hits cannot exceed at-bats.")

    @property
    def batting_average(self):
        return round(self.hits / self.at_bats, 3) if self.at_bats else 0.0
    
    @property
    def on_base_percentage(self):
        plate_appearances = self.at_bats + self.walks
        if not plate_appearances:
            return 0.0
        return round((self.hits + self.walks) / plate_appearances, 3)

    def __str__(self):
        return f"{self.player} — {self.game}"


class PitchingStatLine(models.Model):
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name='pitching_lines')
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='pitching_lines')

    innings_pitched = models.DecimalField(max_digits=4, decimal_places=1, default=0)  # e.g. 5.2
    earned_runs = models.PositiveSmallIntegerField(default=0)
    walks_allowed = models.PositiveSmallIntegerField(default=0)
    strikeouts = models.PositiveSmallIntegerField(default=0)
    hits_allowed = models.PositiveSmallIntegerField(default=0)

    class Meta:
        unique_together = ('player', 'game')

    def clean(self):
      from django.core.exceptions import ValidationError
      if self.strikeouts and self.innings_pitched == 0:
          raise ValidationError("Strikeouts recorded but no innings pitched.")

    @property
    def era(self):
        if not self.innings_pitched:
            return 0.0
        return round((self.earned_runs * 9) / float(self.innings_pitched), 2)
    
    @property
    def whip(self):
        if not self.innings_pitched:
            return 0.0
        return round((self.walks_allowed + self.hits_allowed) / float(self.innings_pitched), 2)

    def __str__(self):
        return f"{self.player} — {self.game}"
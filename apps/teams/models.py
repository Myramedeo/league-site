from django.db import models

class Season(models.Model):
    year = models.PositiveIntegerField(unique=True)
    name = models.CharField(max_length=100, blank=True)  # e.g. "2026 Summer League"

    def __str__(self):
        return self.name or str(self.year)

    class Meta:
        ordering = ['-year']


class Team(models.Model):
    name = models.CharField(max_length=100)
    seasons = models.ManyToManyField(Season, through='players.Roster', related_name='teams')

    def __str__(self):
        return self.name
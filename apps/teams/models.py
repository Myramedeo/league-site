from django.db import models

class Season(models.Model):
    year = models.PositiveIntegerField(unique=True)
    name = models.CharField(max_length=100, blank=True)  # e.g. "2026 Summer League"

    def __str__(self):
        return self.name or str(self.year)

    class Meta:
        ordering = ['-year']


class Competition(models.Model):
    PHASE_CHOICES = [
        ('REGULAR', 'Regular Season'),
        ('PLAYOFFS', 'Playoffs'),
        ('OTHER', 'Other'),
    ]

    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name='competitions')
    name = models.CharField(max_length=150)
    phase = models.CharField(max_length=10, choices=PHASE_CHOICES, default='OTHER')
    legacy_division_id = models.PositiveBigIntegerField(unique=True, null=True, blank=True)
    source_order = models.PositiveIntegerField(null=True, blank=True)
    expected_team_count = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['-season__year', 'source_order', 'name']

    def __str__(self):
        return self.name


class Team(models.Model):
    name = models.CharField(max_length=100)
    seasons = models.ManyToManyField(Season, through='players.Roster', related_name='teams')

    def __str__(self):
        return self.name


class LegacyTeamIdentity(models.Model):
    legacy_team_id = models.PositiveBigIntegerField(unique=True)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='legacy_identities')
    competition = models.ForeignKey(Competition, on_delete=models.CASCADE, related_name='legacy_team_identities')
    source_name = models.CharField(max_length=100)

    def __str__(self):
        return f'{self.source_name} ({self.legacy_team_id})'
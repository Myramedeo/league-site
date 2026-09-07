from django.db.models import Q
from .models import Game

class TeamStanding:
    def __init__(self, team):
        self.team = team
        self.wins = 0
        self.losses = 0
        self.ties = 0
        self.runs_for = 0
        self.runs_against = 0

    @property
    def games_played(self):
        return self.wins + self.losses + self.ties

    @property
    def win_pct(self):
        if not self.games_played:
            return 0.0
        # ties count as half a win, the common convention
        return round((self.wins + 0.5 * self.ties) / self.games_played, 3)
    
    @property
    def win_pct_display(self):
        return f"{self.win_pct:.3f}".lstrip("0")

    def __repr__(self):
        return f"<{self.team}: {self.wins}-{self.losses}-{self.ties}>"


def _standings_from_games(games):
    """Returns a list of TeamStanding objects, sorted best-to-worst, for the given Game queryset."""
    standings = {}

    def get_or_create(team):
        if team.id not in standings:
            standings[team.id] = TeamStanding(team)
        return standings[team.id]

    for game in games.select_related('result', 'home_team', 'away_team'):
        home = get_or_create(game.home_team)
        away = get_or_create(game.away_team)
        winner = game.result.winner

        home.runs_for += game.result.home_score
        home.runs_against += game.result.away_score
        away.runs_for += game.result.away_score
        away.runs_against += game.result.home_score

        if winner is None:
            home.ties += 1
            away.ties += 1
        elif winner == game.home_team:
            home.wins += 1
            away.losses += 1
        else:
            away.wins += 1
            home.losses += 1

    return sorted(standings.values(), key=lambda s: s.win_pct, reverse=True)


def compute_standings(season, competition=None, phase=None):
    """Returns a list of TeamStanding objects, sorted best-to-worst.

    By default this includes every game in the season regardless of
    competition/phase. Pass `competition` or `phase` (e.g. 'REGULAR',
    'PLAYOFFS') to restrict standings to a single competition/phase.
    """
    games = Game.objects.filter(season=season, result__isnull=False)
    if competition is not None:
        games = games.filter(competition=competition)
    if phase is not None:
        games = games.filter(competition__phase=phase)
    return _standings_from_games(games)


def compute_standings_by_phase(season):
    """Returns a list of {'phase', 'label', 'standings'} dicts, one per phase
    that has completed games in the season (regular season, playoffs, etc.),
    in PHASE_CHOICES order, so regular season and playoff standings stay separate."""
    from teams.models import Competition

    results = []
    for phase_key, phase_label in Competition.PHASE_CHOICES:
        games = Game.objects.filter(
            season=season, result__isnull=False, competition__phase=phase_key,
        )
        if not games.exists():
            continue
        results.append({
            'phase': phase_key,
            'label': phase_label,
            'standings': _standings_from_games(games),
        })
    return results
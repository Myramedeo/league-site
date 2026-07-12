from django.db.models import Q
from .models import Game

class TeamStanding:
    def __init__(self, team):
        self.team = team
        self.wins = 0
        self.losses = 0
        self.ties = 0

    @property
    def games_played(self):
        return self.wins + self.losses + self.ties

    @property
    def win_pct(self):
        if not self.games_played:
            return 0.0
        # ties count as half a win, the common convention
        return round((self.wins + 0.5 * self.ties) / self.games_played, 3)

    def __repr__(self):
        return f"<{self.team}: {self.wins}-{self.losses}-{self.ties}>"


def compute_standings(season):
    """Returns a list of TeamStanding objects, sorted best-to-worst."""
    games = (
        Game.objects
        .filter(season=season, result__isnull=False)
        .select_related('result', 'home_team', 'away_team')
    )

    standings = {}

    def get_or_create(team):
        if team.id not in standings:
            standings[team.id] = TeamStanding(team)
        return standings[team.id]

    for game in games:
        home = get_or_create(game.home_team)
        away = get_or_create(game.away_team)
        winner = game.result.winner

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
from django.test import TestCase
from teams.models import Season, Team
from games.models import Game, GameResult
from games.services import compute_standings

class StandingsTests(TestCase):
    def setUp(self):
        self.season = Season.objects.create(year=2026)
        self.team_a = Team.objects.create(name="Hawks")
        self.team_b = Team.objects.create(name="Owls")

    def test_win_loss_recorded_correctly(self):
        game = Game.objects.create(
            season=self.season, home_team=self.team_a,
            away_team=self.team_b, date="2026-06-01"
        )
        GameResult.objects.create(game=game, home_score=5, away_score=2)

        standings = compute_standings(self.season)
        hawks = next(s for s in standings if s.team == self.team_a)
        owls = next(s for s in standings if s.team == self.team_b)

        self.assertEqual(hawks.wins, 1)
        self.assertEqual(hawks.losses, 0)
        self.assertEqual(owls.wins, 0)
        self.assertEqual(owls.losses, 1)
    
    def test_tie_counted_as_half_win(self):
        game = Game.objects.create(
            season=self.season, home_team=self.team_a,
            away_team=self.team_b, date="2026-06-02"
        )
        GameResult.objects.create(game=game, home_score=3, away_score=3)

        standings = compute_standings(self.season)
        hawks = next(s for s in standings if s.team == self.team_a)

        self.assertEqual(hawks.ties, 1)
        self.assertEqual(hawks.win_pct, 0.5)

        owls = next(s for s in standings if s.team == self.team_b)

        self.assertEqual(owls.ties, 1)
        self.assertEqual(owls.win_pct, 0.5)
    
    def test_multiple_games_standings(self):
        # Hawks win 2 games, lose 1
        game1 = Game.objects.create(
            season=self.season, home_team=self.team_a,
            away_team=self.team_b, date="2026-06-01"
        )
        GameResult.objects.create(game=game1, home_score=5, away_score=2)

        game2 = Game.objects.create(
            season=self.season, home_team=self.team_b,
            away_team=self.team_a, date="2026-06-02"
        )
        GameResult.objects.create(game=game2, home_score=3, away_score=4)

        game3 = Game.objects.create(
            season=self.season, home_team=self.team_a,
            away_team=self.team_b, date="2026-06-03"
        )
        GameResult.objects.create(game=game3, home_score=2, away_score=5)

        standings = compute_standings(self.season)
        hawks = next(s for s in standings if s.team == self.team_a)
        owls = next(s for s in standings if s.team == self.team_b)

        self.assertEqual(hawks.wins, 2)
        self.assertEqual(hawks.losses, 1)
        self.assertEqual(owls.wins, 1)
        self.assertEqual(owls.losses, 2)


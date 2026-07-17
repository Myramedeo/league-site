from datetime import time

from django.test import TestCase
from teams.models import Season, Team
from games.models import Game, GameResult
from games.serializers import GameSerializer
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

    def test_game_can_store_scheduled_time(self):
        game = Game.objects.create(
            season=self.season, home_team=self.team_a,
            away_team=self.team_b, date="2026-06-03",
            scheduled_time=time(18, 30)
        )

        self.assertEqual(game.scheduled_time, time(18, 30))

    def test_serializer_exposes_scheduled_time(self):
        game = Game.objects.create(
            season=self.season, home_team=self.team_a,
            away_team=self.team_b, date="2026-06-04",
            scheduled_time=time(19, 0)
        )

        serializer = GameSerializer(game)

        self.assertEqual(serializer.data['scheduled_time'], '19:00:00')

    def test_game_defaults_to_tbp_status(self):
        game = Game.objects.create(
            season=self.season, home_team=self.team_a,
            away_team=self.team_b, date="2026-06-05"
        )

        self.assertEqual(game.status, 'TBP')

    def test_serializer_exposes_status(self):
        game = Game.objects.create(
            season=self.season, home_team=self.team_a,
            away_team=self.team_b, date="2026-06-06",
            status='W'
        )

        serializer = GameSerializer(game)

        self.assertEqual(serializer.data['status'], 'W')

    def test_game_can_store_optional_venue(self):
        game = Game.objects.create(
            season=self.season, home_team=self.team_a,
            away_team=self.team_b, date="2026-06-07",
            venue="Main Field"
        )

        self.assertEqual(game.venue, "Main Field")

    def test_serializer_exposes_venue(self):
        game = Game.objects.create(
            season=self.season, home_team=self.team_a,
            away_team=self.team_b, date="2026-06-08",
            venue="West Diamond"
        )

        serializer = GameSerializer(game)

        self.assertEqual(serializer.data['venue'], 'West Diamond')
        
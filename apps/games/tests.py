from datetime import time
from types import SimpleNamespace

from django.contrib import admin
from django.test import TestCase
from django.urls import reverse
from game_entry.models import BattingSlot, GameScorecard
from players.models import Player, Roster
from stats.models import BattingStatLine
from teams.models import Season, Team
from games.admin import InningScoreInline
from games.models import Game, GameResult, InningScore
from games.serializers import GameSerializer
from games.services import compute_standings


class GameResultTests(TestCase):
    def setUp(self):
        self.season = Season.objects.create(year=2026)
        self.team_a = Team.objects.create(name="Hawks")
        self.team_b = Team.objects.create(name="Owls")

    def create_result(self, game, home_runs, away_runs, **fields):
        result = GameResult.objects.create(game=game, **fields)
        InningScore.objects.bulk_create([
            InningScore(result=result, inning=inning, home_runs=home, away_runs=away)
            for inning, (home, away) in enumerate(zip(home_runs, away_runs), start=1)
        ])
        return result

    def test_result_totals_runs_across_nine_innings(self):
        game = Game.objects.create(
            season=self.season, home_team=self.team_a,
            away_team=self.team_b, date="2026-06-09"
        )
        result = self.create_result(
            game,
            [0, 1, 0, 2, 0, 0, 1, 0, 0],
            [1, 0, 0, 0, 2, 0, 0, 0, 0],
        )

        self.assertEqual(result.home_score, 4)
        self.assertEqual(result.away_score, 3)
        self.assertEqual(result.winner, self.team_a)

    def test_result_uses_inning_totals_when_no_explicit_score_provided(self):
        game = Game.objects.create(
            season=self.season, home_team=self.team_a,
            away_team=self.team_b, date="2026-06-10"
        )
        result = self.create_result(
            game,
            [1, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 0],
        )

        self.assertEqual(result.home_score, 1)
        self.assertEqual(result.away_score, 0)

    def test_game_detail_page_renders_result_and_stat_lines(self):
        game = Game.objects.create(
            season=self.season, home_team=self.team_a,
            away_team=self.team_b, date="2026-06-11",
            venue="Main Field",
        )
        self.create_result(
            game,
            [0, 1, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0, 0, 0, 0, 1],
            final_home_score=1,
            final_away_score=1,
        )

        response = self.client.get(reverse('game_detail', args=[game.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Main Field')
        self.assertEqual(response.context['result'].home_score, 1)
        self.assertEqual(response.context['result'].away_score, 1)

    def test_game_detail_orders_batting_lines_by_existing_lineup(self):
        game = Game.objects.create(
            season=self.season, home_team=self.team_a,
            away_team=self.team_b, date="2026-06-11",
        )
        self.create_result(game, [0], [0], final_home_score=0, final_away_score=0)
        first_batter = Player.objects.create(first_name='Zoe', last_name='Alpha')
        second_batter = Player.objects.create(first_name='Amy', last_name='Zulu')
        Roster.objects.create(player=first_batter, team=self.team_b, season=self.season)
        Roster.objects.create(player=second_batter, team=self.team_b, season=self.season)
        BattingStatLine.objects.create(player=first_batter, game=game)
        BattingStatLine.objects.create(player=second_batter, game=game)

        scorecard = GameScorecard.objects.create(game=game)
        BattingSlot.objects.create(scorecard=scorecard, team=self.team_b, order=1, player=second_batter)
        BattingSlot.objects.create(scorecard=scorecard, team=self.team_b, order=2, player=first_batter)

        response = self.client.get(reverse('game_detail', args=[game.id]))

        self.assertEqual(
            [line.player for line in response.context['away_batting_lines']],
            [second_batter, first_batter],
        )

    def test_game_detail_shows_hidden_multi_team_player_under_scorecard_team(self):
        game = Game.objects.create(
            season=self.season, home_team=self.team_a,
            away_team=self.team_b, date='2026-06-11',
        )
        self.create_result(game, [0], [0], final_home_score=0, final_away_score=0)
        player = Player.objects.create(first_name='Casey', last_name='Guest')
        Roster.objects.create(player=player, team=self.team_a, season=self.season)
        Roster.objects.create(
            player=player,
            team=self.team_b,
            season=self.season,
            show_in_team_list=False,
        )
        BattingStatLine.objects.create(player=player, game=game)

        scorecard = GameScorecard.objects.create(game=game)
        BattingSlot.objects.create(scorecard=scorecard, team=self.team_b, order=1, player=player)

        response = self.client.get(reverse('game_detail', args=[game.id]))

        self.assertEqual(response.context['home_batting_lines'], [])
        self.assertEqual([line.player for line in response.context['away_batting_lines']], [player])

    def test_game_detail_page_renders_scheduled_game_without_result(self):
        game = Game.objects.create(
            season=self.season,
            home_team=self.team_a,
            away_team=self.team_b,
            date='2026-06-12',
            scheduled_time=time(18, 30),
        )

        response = self.client.get(reverse('game_detail', args=[game.id]))

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context['result'])
        self.assertContains(response, 'Hawks')
        self.assertContains(response, 'Owls')
        self.assertContains(response, 'To be played')
        self.assertContains(response, 'This game has not been completed yet.')

    def test_inning_score_inline_only_adds_missing_forms_for_existing_result(self):
        class DummyQuerySet:
            def count(self):
                return 2

        inline = InningScoreInline(InningScore, admin.site)
        result = SimpleNamespace(innings=DummyQuerySet())

        self.assertEqual(inline.get_extra(None, result), 7)

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
        GameResult.objects.create(game=game, final_home_score=5, final_away_score=2)

        standings = compute_standings(self.season)
        hawks = next(s for s in standings if s.team == self.team_a)
        owls = next(s for s in standings if s.team == self.team_b)

        self.assertEqual(hawks.wins, 1)
        self.assertEqual(hawks.losses, 0)
        self.assertEqual(hawks.runs_for, 5)
        self.assertEqual(hawks.runs_against, 2)
        self.assertEqual(owls.wins, 0)
        self.assertEqual(owls.losses, 1)
        self.assertEqual(owls.runs_for, 2)
        self.assertEqual(owls.runs_against, 5)

    def test_tie_counted_as_half_win(self):
        game = Game.objects.create(
            season=self.season, home_team=self.team_a,
            away_team=self.team_b, date="2026-06-02"
        )
        GameResult.objects.create(game=game, final_home_score=3, final_away_score=3)

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
        
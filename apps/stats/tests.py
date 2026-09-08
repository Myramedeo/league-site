from django.test import TestCase
from teams.models import Season, Team
from games.models import Game, GameResult
from games.services import compute_standings
from players.models import Player, Roster
from stats.models import BattingStatLine
from stats.services import team_batting_stats

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
        self.assertEqual(owls.wins, 0)
        self.assertEqual(owls.losses, 1)
    
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

        owls = next(s for s in standings if s.team == self.team_b)

        self.assertEqual(owls.ties, 1)
        self.assertEqual(owls.win_pct, 0.5)
    
    def test_multiple_games_standings(self):
        # Hawks win 2 games, lose 1
        game1 = Game.objects.create(
            season=self.season, home_team=self.team_a,
            away_team=self.team_b, date="2026-06-01"
        )
        GameResult.objects.create(game=game1, final_home_score=5, final_away_score=2)

        game2 = Game.objects.create(
            season=self.season, home_team=self.team_b,
            away_team=self.team_a, date="2026-06-02"
        )
        GameResult.objects.create(game=game2, final_home_score=3, final_away_score=4)

        game3 = Game.objects.create(
            season=self.season, home_team=self.team_a,
            away_team=self.team_b, date="2026-06-03"
        )
        GameResult.objects.create(game=game3, final_home_score=2, final_away_score=5)

        standings = compute_standings(self.season)
        hawks = next(s for s in standings if s.team == self.team_a)
        owls = next(s for s in standings if s.team == self.team_b)

        self.assertEqual(hawks.wins, 2)
        self.assertEqual(hawks.losses, 1)
        self.assertEqual(owls.wins, 1)
        self.assertEqual(owls.losses, 2)


class BattingStatLineTests(TestCase):
    def setUp(self):
        self.season = Season.objects.create(year=2026)
        self.team_a = Team.objects.create(name='Hawks')
        self.team_b = Team.objects.create(name='Owls')

    def test_on_base_percentage_includes_walks_hit_by_pitch_and_sacrifices(self):
        player = Player.objects.create(first_name='Casey', last_name='Batter')
        game = Game.objects.create(
            season=self.season,
            home_team=self.team_a,
            away_team=self.team_b,
            date='2026-06-03',
        )
        line = BattingStatLine.objects.create(
            player=player,
            game=game,
            at_bats=6,
            hits=2,
            walks=1,
            hit_by_pitch=1,
            sacrifices=1,
        )

        self.assertEqual(line.on_base_percentage, 0.444)


class TeamBattingStatsTests(TestCase):
    def setUp(self):
        self.season = Season.objects.create(year=2026)
        self.team = Team.objects.create(name="Hawks")

    def test_aggregates_across_games_and_includes_zero_stat_players(self):
        batter = Player.objects.create(first_name='Casey', last_name='Batter')
        bench = Player.objects.create(first_name='Sam', last_name='Bench')
        Roster.objects.create(player=batter, team=self.team, season=self.season)
        Roster.objects.create(player=bench, team=self.team, season=self.season)

        opponent = Team.objects.create(name="Owls")
        game1 = Game.objects.create(season=self.season, home_team=self.team, away_team=opponent, date='2026-06-01')
        game2 = Game.objects.create(season=self.season, home_team=self.team, away_team=opponent, date='2026-06-08')
        BattingStatLine.objects.create(player=batter, game=game1, at_bats=4, hits=2, runs=1, rbis=1)
        BattingStatLine.objects.create(player=batter, game=game2, at_bats=3, hits=1, walks=1)

        results = team_batting_stats(self.team, self.season)
        by_player = {r['player']: r for r in results}

        self.assertEqual(by_player[batter]['at_bats'], 7)
        self.assertEqual(by_player[batter]['hits'], 3)
        self.assertEqual(by_player[batter]['batting_average'], round(3 / 7, 3))
        self.assertEqual(by_player[bench]['at_bats'], 0)
        self.assertEqual(by_player[bench]['batting_average'], 0.0)

    def test_player_with_multiple_roster_rows_not_double_counted(self):
        from teams.models import Competition

        batter = Player.objects.create(first_name='Casey', last_name='Batter')
        competition_a = Competition.objects.create(name='Regular Season', season=self.season)
        competition_b = Competition.objects.create(name='Playoffs', season=self.season)
        Roster.objects.create(player=batter, team=self.team, season=self.season, competition=competition_a)
        Roster.objects.create(player=batter, team=self.team, season=self.season, competition=competition_b)

        opponent = Team.objects.create(name="Owls")
        game = Game.objects.create(season=self.season, home_team=self.team, away_team=opponent, date='2026-06-01')
        BattingStatLine.objects.create(player=batter, game=game, at_bats=4, hits=2)

        results = team_batting_stats(self.team, self.season)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['at_bats'], 4)



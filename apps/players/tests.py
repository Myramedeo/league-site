from django.test import TestCase
from django.urls import reverse

from games.models import Game
from stats.models import BattingStatLine

from players.models import LegacyPlayerIdentity, Player, Roster
from players.services import find_duplicate_players, merge_players
from teams.models import Season, Team


class PlayerDetailTests(TestCase):
	def setUp(self):
		self.player = Player.objects.create(first_name='Test', last_name='Player')
		self.team = Team.objects.create(name='Test Team')
		self.older_season = Season.objects.create(year=2025)
		self.newer_season = Season.objects.create(year=2026)

	def create_stat_line(self, season, **stats):
		game = Game.objects.create(
			season=season,
			home_team=self.team,
			away_team=Team.objects.create(name=f'Away {season.year}'),
			date=f'{season.year}-06-01',
		)
		return BattingStatLine.objects.create(player=self.player, game=game, **stats)

	def test_player_detail_groups_stats_by_season_and_adds_overall_row(self):
		self.create_stat_line(self.older_season, at_bats=10, hits=3, singles=2, doubles=1, rbis=2)
		self.create_stat_line(self.newer_season, at_bats=20, hits=10, singles=8, doubles=2, rbis=4)

		response = self.client.get(reverse('player_detail', args=[self.player.id]))

		stats = response.context['batting_stats']
		self.assertEqual([row['season'] for row in stats], ['2026', '2025', 'Overall'])
		self.assertEqual(stats[-1]['at_bats'], 30)
		self.assertEqual(stats[-1]['hits'], 13)
		self.assertEqual(stats[-1]['batting_average'], 13 / 30)
		self.assertContains(response, 'Batting Statistics')
		self.assertContains(response, 'Overall')


class PlayerMergeTests(TestCase):
	def test_find_duplicate_players_finds_similar_names(self):
		Player.objects.create(first_name='John', last_name='Smith')
		Player.objects.create(first_name='Johnny', last_name='Smith')
		Player.objects.create(first_name='Jane', last_name='Doe')

		matches = find_duplicate_players(threshold=0.75)
		self.assertTrue(any(m['left'].last_name == 'Smith' and m['right'].first_name == 'Johnny' for m in matches))
		self.assertEqual(len(matches), 1)

	def test_merge_players_combines_stats_and_rosters(self):
		season = Season.objects.create(year=2026)
		target = Player.objects.create(first_name='John', last_name='Smith', jersey_number=7)
		source = Player.objects.create(first_name='Johnny', last_name='Smith', jersey_number=99)
		team = Team.objects.create(name='Hawks')
		other_team = Team.objects.create(name='Owls')
		LegacyPlayerIdentity.objects.create(legacy_player_id=101, player=source, source_first_name='Johnny', source_last_name='Smith')
		Roster.objects.create(player=target, team=team, season=season)
		Roster.objects.create(player=source, team=team, season=season)
		Roster.objects.create(player=source, team=other_team, season=season)

		shared_game = Game.objects.create(season=season, home_team=team, away_team=other_team, date='2026-06-01')
		BattingStatLine.objects.create(player=target, game=shared_game, at_bats=4, hits=2, singles=2, doubles=0, triples=0, home_runs=0, runs=1, rbis=1)
		BattingStatLine.objects.create(player=source, game=shared_game, at_bats=3, hits=1, singles=1, doubles=0, triples=0, home_runs=0, runs=0, rbis=1)
		other_game = Game.objects.create(season=season, home_team=other_team, away_team=team, date='2026-06-03')
		BattingStatLine.objects.create(player=source, game=other_game, at_bats=2, hits=1, singles=1, doubles=0, triples=0, home_runs=0, runs=0, rbis=0)

		merge_players(target, source)

		self.assertFalse(Player.objects.filter(pk=source.pk).exists())
		self.assertEqual(BattingStatLine.objects.filter(player=target, game=shared_game).count(), 1)
		self.assertEqual(BattingStatLine.objects.filter(player=target, game=other_game).count(), 1)
		self.assertEqual(BattingStatLine.objects.get(player=target, game=shared_game).at_bats, 7)
		self.assertEqual(BattingStatLine.objects.get(player=target, game=shared_game).hits, 3)
		self.assertEqual(BattingStatLine.objects.get(player=target, game=other_game).at_bats, 2)
		self.assertEqual(Roster.objects.filter(player=target, team=team, season=season).count(), 1)
		self.assertEqual(Roster.objects.filter(player=target, team=other_team, season=season).count(), 1)
		self.assertEqual(LegacyPlayerIdentity.objects.filter(player=target).count(), 1)

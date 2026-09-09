from django.test import TestCase
from django.urls import reverse

from games.models import Game
from stats.models import BattingStatLine

from players.models import Player
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

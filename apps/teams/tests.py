from django.test import TestCase
from django.urls import reverse

from players.models import Player, Roster

from .models import Season, Team


class TeamListTests(TestCase):
	def setUp(self):
		self.previous_season = Season.objects.create(year=2025)
		self.current_season = Season.objects.create(year=2026)
		self.previous_team = Team.objects.create(name='Previous Team')
		self.current_team = Team.objects.create(name='Current Team')
		player = Player.objects.create(first_name='Test', last_name='Player')
		Roster.objects.create(player=player, team=self.previous_team, season=self.previous_season)
		Roster.objects.create(player=player, team=self.current_team, season=self.current_season)

	def test_team_list_defaults_to_the_latest_season(self):
		response = self.client.get(reverse('team_list'))

		self.assertContains(response, 'Current Team')
		self.assertNotContains(response, 'Previous Team')
		self.assertEqual(response.context['season'], self.current_season)

	def test_team_list_filters_by_selected_season(self):
		response = self.client.get(reverse('team_list'), {'season': self.previous_season.year})

		self.assertContains(response, 'Previous Team')
		self.assertNotContains(response, 'Current Team')
		self.assertEqual(response.context['season'], self.previous_season)

	def test_team_list_defaults_to_first_team_and_shows_batting_stats(self):
		response = self.client.get(reverse('team_list'))

		self.assertEqual(response.context['selected_team'], self.current_team)
		self.assertEqual(len(response.context['batting_stats']), 1)
		self.assertEqual(response.context['batting_stats'][0]['at_bats'], 0)
		self.assertContains(response, '.000')

	def test_team_list_switches_team_via_query_param(self):
		response = self.client.get(reverse('team_list'), {
			'season': self.previous_season.year,
			'team': self.previous_team.id,
		})

		self.assertEqual(response.context['selected_team'], self.previous_team)
		self.assertContains(response, 'Previous Team')

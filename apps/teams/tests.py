from django.test import TestCase
from django.urls import reverse

from players.models import Player, Roster

from teams.models import Competition, Season, Team


class TeamListTests(TestCase):
	def setUp(self):
		self.previous_season = Season.objects.create(year=2025)
		self.current_season = Season.objects.create(year=2026)
		self.previous_competition = Competition.objects.create(name='2025 Regular Season', season=self.previous_season)
		self.current_competition = Competition.objects.create(name='2026 Regular Season', season=self.current_season)
		self.previous_team = Team.objects.create(name='Previous Team')
		self.current_team = Team.objects.create(name='Current Team')
		player = Player.objects.create(first_name='Test', last_name='Player')
		Roster.objects.create(player=player, team=self.previous_team, season=self.previous_season, competition=self.previous_competition)
		Roster.objects.create(player=player, team=self.current_team, season=self.current_season, competition=self.current_competition)

	def test_team_list_defaults_to_the_latest_competition(self):
		response = self.client.get(reverse('team_list'))

		self.assertContains(response, 'Current Team')
		self.assertNotContains(response, 'Previous Team')
		self.assertEqual(response.context['competition'], self.current_competition)

	def test_team_list_filters_by_selected_competition(self):
		response = self.client.get(reverse('team_list'), {'competition': self.previous_competition.id})

		self.assertContains(response, 'Previous Team')
		self.assertNotContains(response, 'Current Team')
		self.assertEqual(response.context['competition'], self.previous_competition)

	def test_team_list_defaults_to_first_team_and_shows_batting_stats(self):
		response = self.client.get(reverse('team_list'))

		self.assertEqual(response.context['selected_team'], self.current_team)
		self.assertEqual(len(response.context['batting_stats']), 1)
		self.assertEqual(response.context['batting_stats'][0]['at_bats'], 0)
		self.assertContains(response, '.000')

	def test_team_list_switches_team_via_query_param(self):
		response = self.client.get(reverse('team_list'), {
			'competition': self.previous_competition.id,
			'team': self.previous_team.id,
		})

		self.assertEqual(response.context['selected_team'], self.previous_team)
		self.assertContains(response, 'Previous Team')

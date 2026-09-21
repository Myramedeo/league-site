from unittest.mock import Mock

from django.contrib.admin import AdminSite
from django.test import RequestFactory, TestCase
from django.urls import reverse

from players.models import Player, Roster

from teams.admin import CompetitionAdmin, copy_regular_rosters_to_playoffs
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


class CopyRegularRostersToPlayoffsTests(TestCase):
	def setUp(self):
		self.factory = RequestFactory()
		self.site = AdminSite()
		self.modeladmin = CompetitionAdmin(Competition, self.site)
		self.season = Season.objects.create(year=2026)
		self.regular = Competition.objects.create(
			name='2026 Regular Season',
			season=self.season,
			phase='REGULAR',
		)
		self.playoffs = Competition.objects.create(
			name='2026 Playoffs',
			season=self.season,
			phase='PLAYOFFS',
		)
		self.team = Team.objects.create(name='Hawks')
		self.player = Player.objects.create(first_name='Test', last_name='Player')
		self.hidden_player = Player.objects.create(first_name='Hidden', last_name='Player')
		Roster.objects.create(
			player=self.player,
			team=self.team,
			season=self.season,
			competition=self.regular,
		)
		Roster.objects.create(
			player=self.hidden_player,
			team=self.team,
			season=self.season,
			competition=self.regular,
			show_in_team_list=False,
		)

	def request(self, data):
		request = self.factory.post(reverse('admin:teams_competition_changelist'), data)
		request.user = Mock(is_active=True, is_staff=True, is_superuser=True)
		return request

	def run_action(self, request, queryset=None):
		self.modeladmin.message_user = Mock()
		return copy_regular_rosters_to_playoffs(
			self.modeladmin,
			request,
			queryset or Competition.objects.filter(pk=self.playoffs.pk),
		)

	def test_confirmation_page_lists_same_season_regular_competitions(self):
		request = self.request({
			'action': 'copy_regular_rosters_to_playoffs',
			'_selected_action': str(self.playoffs.pk),
		})

		response = self.run_action(request)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(list(response.context_data['regular_competitions']), [self.regular])
		self.assertEqual(response.context_data['target'], self.playoffs)

	def test_action_copies_rosters_and_preserves_visibility(self):
		request = self.request({
			'action': 'copy_regular_rosters_to_playoffs',
			'_selected_action': str(self.playoffs.pk),
			'source_competition_id': str(self.regular.pk),
			'confirm_copy': '1',
		})

		response = self.run_action(request)

		self.assertEqual(response.status_code, 302)
		self.assertEqual(Roster.objects.filter(competition=self.playoffs).count(), 2)
		self.assertFalse(
			Roster.objects.get(
				competition=self.playoffs,
				player=self.hidden_player,
			).show_in_team_list
		)
		self.modeladmin.message_user.assert_called_once()
		self.assertIn('Copied 2 roster record(s)', self.modeladmin.message_user.call_args.args[1])

	def test_action_skips_existing_rows_when_repeated(self):
		Roster.objects.create(
			player=self.player,
			team=self.team,
			season=self.season,
			competition=self.playoffs,
		)

		request = self.request({
			'action': 'copy_regular_rosters_to_playoffs',
			'_selected_action': str(self.playoffs.pk),
			'source_competition_id': str(self.regular.pk),
			'confirm_copy': '1',
		})
		self.run_action(request)

		self.assertEqual(Roster.objects.filter(competition=self.playoffs).count(), 2)
		self.assertIn('Copied 1 roster record(s)', self.modeladmin.message_user.call_args.args[1])

		request = self.request({
			'action': 'copy_regular_rosters_to_playoffs',
			'_selected_action': str(self.playoffs.pk),
			'source_competition_id': str(self.regular.pk),
			'confirm_copy': '1',
		})
		self.run_action(request)

		self.assertEqual(Roster.objects.filter(competition=self.playoffs).count(), 2)
		self.assertIn('Copied 0 roster record(s)', self.modeladmin.message_user.call_args.args[1])

	def test_action_rejects_non_playoffs_target(self):
		request = self.request({
			'action': 'copy_regular_rosters_to_playoffs',
			'_selected_action': str(self.regular.pk),
		})

		self.run_action(request, Competition.objects.filter(pk=self.regular.pk))

		self.modeladmin.message_user.assert_called_once()
		self.assertIn('must be a Playoffs competition', self.modeladmin.message_user.call_args.args[1])

	def test_action_rejects_source_from_another_season(self):
		other_season = Season.objects.create(year=2025)
		other_regular = Competition.objects.create(
			name='2025 Regular Season',
			season=other_season,
			phase='REGULAR',
		)
		request = self.request({
			'action': 'copy_regular_rosters_to_playoffs',
			'_selected_action': str(self.playoffs.pk),
			'source_competition_id': str(other_regular.pk),
			'confirm_copy': '1',
		})

		self.run_action(request)

		self.assertEqual(Roster.objects.filter(competition=self.playoffs).count(), 0)
		self.assertIn('valid Regular Season competition', self.modeladmin.message_user.call_args.args[1])

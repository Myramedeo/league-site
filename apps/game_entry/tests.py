from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from games.models import Game
from teams.models import Season, Team


class GameEntryPortalTests(TestCase):
	def setUp(self):
		self.user_model = get_user_model()
		self.url = reverse('game_entry:portal')
		self.staff_user = self.user_model.objects.create_user(
			username='scorekeeper',
			password='test-pass-123',
			is_staff=True,
		)
		self.current_season = Season.objects.create(year=2026)
		self.previous_season = Season.objects.create(year=2025)
		self.hawks = Team.objects.create(name='Hawks')
		self.owls = Team.objects.create(name='Owls')
		self.bears = Team.objects.create(name='Bears')

	def test_staff_user_can_access_portal(self):
		self.client.force_login(self.staff_user)

		response = self.client.get(self.url)

		self.assertEqual(response.status_code, 200)
		self.assertTemplateUsed(response, 'game_entry/portal.html')
		self.assertContains(response, 'Select a Game')

	def test_portal_lists_only_current_season_games(self):
		current_game = Game.objects.create(
			season=self.current_season,
			home_team=self.hawks,
			away_team=self.owls,
			date='2026-07-12',
			venue='North Field',
		)
		Game.objects.create(
			season=self.previous_season,
			home_team=self.hawks,
			away_team=self.bears,
			date='2025-07-12',
			venue='Archive Field',
		)

		self.client.force_login(self.staff_user)
		response = self.client.get(self.url)

		self.assertContains(response, 'North Field')
		self.assertContains(response, 'Hawks')
		self.assertContains(response, 'Owls')
		self.assertNotContains(response, 'Archive Field')
		self.assertContains(response, reverse('game_entry:game_workspace', args=[current_game.id]))

	def test_anonymous_user_redirected_to_admin_login(self):
		response = self.client.get(self.url)

		self.assertEqual(response.status_code, 302)
		self.assertIn(reverse('admin:login'), response.url)

	def test_non_staff_user_redirected_to_admin_login(self):
		non_staff_user = self.user_model.objects.create_user(
			username='player',
			password='test-pass-123',
			is_staff=False,
		)
		self.client.force_login(non_staff_user)

		response = self.client.get(self.url)

		self.assertEqual(response.status_code, 302)
		self.assertIn(reverse('admin:login'), response.url)

	def test_staff_user_can_open_game_workspace(self):
		game = Game.objects.create(
			season=self.current_season,
			home_team=self.hawks,
			away_team=self.owls,
			date='2026-07-13',
		)
		self.client.force_login(self.staff_user)

		response = self.client.get(reverse('game_entry:game_workspace', args=[game.id]))

		self.assertEqual(response.status_code, 200)
		self.assertTemplateUsed(response, 'game_entry/game_workspace.html')
		self.assertContains(response, 'Scoring Workspace')

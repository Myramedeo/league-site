from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from games.models import Game
from players.models import Player, Roster
from teams.models import Season, Team

from game_entry.models import LineupSubstitution, PlateAppearance, ScoringSession, TeamLineup


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


class LineupStateAndSubstitutionTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.staff_user = self.user_model.objects.create_user(
            username='entry_staff',
            password='test-pass-123',
            is_staff=True,
        )
        self.season = Season.objects.create(year=2026)
        self.hawks = Team.objects.create(name='Hawks')
        self.owls = Team.objects.create(name='Owls')
        self.game = Game.objects.create(
            season=self.season,
            home_team=self.hawks,
            away_team=self.owls,
            date='2026-07-20',
        )

        self.away_players = [
            Player.objects.create(first_name='Away', last_name=f'Player{i}')
            for i in range(1, 5)
        ]
        self.home_players = [
            Player.objects.create(first_name='Home', last_name=f'Player{i}')
            for i in range(1, 5)
        ]

        for player in self.away_players:
            Roster.objects.create(player=player, team=self.owls, season=self.season)
        for player in self.home_players:
            Roster.objects.create(player=player, team=self.hawks, season=self.season)

        self.workspace_url = reverse('game_entry:game_workspace', args=[self.game.id])

    def _lineup_post_data(self):
        data = {
            'action': 'save_lineups',
            'away-lineup_size': '3',
            'home-lineup_size': '3',
        }
        for index, player in enumerate(self.away_players[:3], start=1):
            data[f'away-spot_{index}'] = str(player.id)
        for index, player in enumerate(self.home_players[:3], start=1):
            data[f'home-spot_{index}'] = str(player.id)
        return data

    def _start_scoring(self):
        self.client.post(self.workspace_url, self._lineup_post_data())
        self.client.post(self.workspace_url, {
            'action': 'record_plate_appearance',
            'offense_team': 'away',
            'result': 'BB',
            'notes': 'Lead-off walk',
        })

    def test_staff_can_save_lineups_before_start(self):
        self.client.force_login(self.staff_user)

        response = self.client.post(self.workspace_url, self._lineup_post_data())

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.workspace_url)

        session = ScoringSession.objects.get(game=self.game)
        away_lineup = TeamLineup.objects.get(session=session, team=self.owls)
        home_lineup = TeamLineup.objects.get(session=session, team=self.hawks)
        self.assertEqual(away_lineup.spots.count(), 3)
        self.assertEqual(home_lineup.spots.count(), 3)
        self.assertFalse(session.lineups_locked)
        self.assertIsNone(session.started_at)

    def test_recording_plate_appearance_rotates_batter_and_locks_lineup(self):
        self.client.force_login(self.staff_user)
        self.client.post(self.workspace_url, self._lineup_post_data())

        session = ScoringSession.objects.get(game=self.game)
        away_lineup = TeamLineup.objects.get(session=session, team=self.owls)
        first_batter = away_lineup.current_batter

        response = self.client.post(self.workspace_url, {
            'action': 'record_plate_appearance',
            'offense_team': 'away',
            'result': 'BB',
            'notes': 'Lead-off walk',
        })
        self.assertEqual(response.status_code, 302)

        away_lineup.refresh_from_db()
        session.refresh_from_db()
        self.assertEqual(away_lineup.batting_index, 1)
        self.assertNotEqual(first_batter, away_lineup.current_batter)
        self.assertTrue(session.lineups_locked)
        self.assertIsNotNone(session.started_at)

        pa = PlateAppearance.objects.get(session=session)
        self.assertEqual(pa.batter, first_batter)
        self.assertEqual(pa.result, 'BB')

    def test_plate_appearance_captures_inning_out_and_base_context(self):
        self.client.force_login(self.staff_user)
        self.client.post(self.workspace_url, self._lineup_post_data())

        self.client.post(self.workspace_url, {
            'action': 'update_game_state',
            'state-current_inning': '2',
            'state-half_inning': 'BOT',
            'state-outs': '1',
            'state-first_base_runner': str(self.home_players[0].id),
            'state-second_base_runner': str(self.home_players[1].id),
            'state-third_base_runner': '',
        })

        self.client.post(self.workspace_url, {
            'action': 'record_plate_appearance',
            'offense_team': 'home',
            'result': '1B',
            'notes': 'RBI single',
        })

        session = ScoringSession.objects.get(game=self.game)
        pa = PlateAppearance.objects.filter(session=session).latest('id')
        self.assertEqual(pa.inning_number, 2)
        self.assertEqual(pa.half_inning, 'BOT')
        self.assertEqual(pa.outs_before, 1)
        self.assertEqual(pa.first_base_runner_before, self.home_players[0])
        self.assertEqual(pa.second_base_runner_before, self.home_players[1])
        self.assertIsNone(pa.third_base_runner_before)

    def test_lineups_cannot_be_resaved_after_scoring_starts(self):
        self.client.force_login(self.staff_user)
        self._start_scoring()

        session = ScoringSession.objects.get(game=self.game)
        away_lineup = TeamLineup.objects.get(session=session, team=self.owls)
        original_first_spot = away_lineup.spots.get(batting_order=1).player_id

        post_data = self._lineup_post_data()
        post_data['away-spot_1'] = str(self.away_players[3].id)
        response = self.client.post(self.workspace_url, post_data)

        self.assertEqual(response.status_code, 302)
        away_lineup.refresh_from_db()
        self.assertEqual(away_lineup.spots.get(batting_order=1).player_id, original_first_spot)

    def test_substitution_allowed_after_lineups_are_locked(self):
        self.client.force_login(self.staff_user)
        self._start_scoring()

        session = ScoringSession.objects.get(game=self.game)
        away_lineup = TeamLineup.objects.get(session=session, team=self.owls)
        old_player = away_lineup.spots.get(batting_order=2).player

        response = self.client.post(self.workspace_url, {
            'action': 'substitute_away',
            'away_sub-batting_order': '2',
            'away_sub-incoming_player': str(self.away_players[3].id),
            'away_sub-notes': 'Pinch hitter',
        })

        self.assertEqual(response.status_code, 302)
        away_lineup.refresh_from_db()
        new_player = away_lineup.spots.get(batting_order=2).player
        self.assertEqual(new_player, self.away_players[3])
        self.assertNotEqual(old_player, new_player)

        substitution = LineupSubstitution.objects.get(session=session)
        self.assertEqual(substitution.outgoing_player, old_player)
        self.assertEqual(substitution.incoming_player, new_player)
        self.assertEqual(substitution.batting_order, 2)

    def test_duplicate_player_in_lineup_returns_validation_error(self):
        self.client.force_login(self.staff_user)
        data = self._lineup_post_data()
        data['away-spot_2'] = str(self.away_players[0].id)

        response = self.client.post(self.workspace_url, data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'already in the lineup')

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from games.models import Game, GameResult
from players.models import Player, Roster
from stats.models import BattingStatLine
from teams.models import Season, Team

from game_entry import services
from game_entry.models import BattingSlot, GameScorecard, ScorecardEntry


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

    def test_portal_shows_unplayed_games_before_completed_games(self):
        completed_game = Game.objects.create(
            season=self.current_season,
            home_team=self.hawks,
            away_team=self.owls,
            date='2026-07-10',
            venue='Completed Field',
            status='F',
        )
        upcoming_game = Game.objects.create(
            season=self.current_season,
            home_team=self.hawks,
            away_team=self.bears,
            date='2026-07-20',
            venue='Upcoming Field',
        )

        self.client.force_login(self.staff_user)
        response = self.client.get(self.url)

        self.assertEqual(list(response.context['upcoming_games']), [upcoming_game])
        self.assertEqual(list(response.context['completed_games']), [completed_game])

    def test_anonymous_user_redirected_to_admin_login(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('game_entry:sign_in'), response.url)

    def test_non_staff_user_redirected_to_admin_login(self):
        non_staff_user = self.user_model.objects.create_user(
            username='player',
            password='test-pass-123',
            is_staff=False,
        )
        self.client.force_login(non_staff_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('game_entry:sign_in'), response.url)

    def test_staff_sign_in_page_renders(self):
        response = self.client.get(reverse('game_entry:sign_in'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'game_entry/sign_in.html')
        self.assertContains(response, 'Staff Sign In')

    def test_staff_sign_in_redirects_to_game_entry_portal(self):
        response = self.client.post(reverse('game_entry:sign_in'), {
            'username': self.staff_user.username,
            'password': 'test-pass-123',
            'next': reverse('game_entry:portal'),
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('game_entry:portal'))

    def test_non_staff_cannot_sign_in_to_game_entry(self):
        non_staff_user = self.user_model.objects.create_user(
            username='bench_player',
            password='test-pass-123',
            is_staff=False,
        )

        response = self.client.post(reverse('game_entry:sign_in'), {
            'username': non_staff_user.username,
            'password': 'test-pass-123',
            'next': reverse('game_entry:portal'),
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'does not have staff access')

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
        self.assertContains(response, 'Scorecard')


class ScorecardWorkflowTests(TestCase):
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
            for i in range(1, 4)
        ]
        self.home_players = [
            Player.objects.create(first_name='Home', last_name=f'Player{i}')
            for i in range(1, 4)
        ]
        for player in self.away_players:
            Roster.objects.create(player=player, team=self.owls, season=self.season)
        for player in self.home_players:
            Roster.objects.create(player=player, team=self.hawks, season=self.season)

        self.client.force_login(self.staff_user)
        self.workspace_url = reverse('game_entry:game_workspace', args=[self.game.id])

    def _set_lineup_slot(self, team_key, order, player):
        url = reverse('game_entry:lineup_slot', args=[self.game.id, team_key, order])
        return self.client.post(url, {f'{team_key}-{order}-player': player.id})

    def _set_lineup(self, team_key, players):
        for order, player in enumerate(players, start=1):
            self._set_lineup_slot(team_key, order, player)

    def _add_play(self, team_key, **fields):
        url = reverse('game_entry:add_play', args=[self.game.id, team_key])
        data = {
            'result': 'OUT',
            'outs_recorded': 1,
            'rbi': 0,
            'batter_ending_base': 'OUT',
            'notation': '',
            'notes': '',
        }
        data.update(fields)
        return self.client.post(url, data)

    def test_staff_user_can_open_workspace(self):
        response = self.client.get(self.workspace_url)
        self.assertEqual(response.status_code, 200)

    def test_lineup_slot_assignment_creates_batting_slot(self):
        response = self._set_lineup_slot('away', 1, self.away_players[0])

        self.assertEqual(response.status_code, 200)
        scorecard = GameScorecard.objects.get(game=self.game)
        slot = BattingSlot.objects.get(scorecard=scorecard, team=self.owls, order=1)
        self.assertEqual(slot.player, self.away_players[0])

    def test_duplicate_player_in_lineup_rejected(self):
        self._set_lineup_slot('away', 1, self.away_players[0])
        response = self._set_lineup_slot('away', 2, self.away_players[0])

        self.assertContains(response, 'already in the lineup')
        self.assertFalse(
            BattingSlot.objects.filter(
                scorecard__game=self.game, team=self.owls, order=2,
            ).exists()
        )

    def test_workspace_renders_unique_select_ids_with_selected_players(self):
        self._set_lineup_slot('away', 1, self.away_players[0])
        self._set_lineup_slot('home', 1, self.home_players[0])

        response = self.client.get(self.workspace_url)
        content = response.content.decode()

        # Each row's select must have a unique name/id so browser form-value
        # restoration on reload can't apply one row's value to another row.
        self.assertContains(response, 'id="id_away-1-player"')
        self.assertContains(response, 'id="id_home-1-player"')
        self.assertNotIn('id="id_player"', content)
        self.assertContains(response, f'<option value="{self.away_players[0].id}" selected>')
        self.assertContains(response, f'<option value="{self.home_players[0].id}" selected>')

    def test_add_play_records_current_batter_and_rotates(self):
        self._set_lineup('away', self.away_players[:2])

        response = self._add_play('away', result='BB', outs_recorded=0, rbi=0, batter_ending_base='1B')
        self.assertEqual(response.status_code, 200)

        entry = ScorecardEntry.objects.get(scorecard__game=self.game)
        self.assertEqual(entry.slot.player, self.away_players[0])
        self.assertEqual(entry.inning, 1)
        self.assertEqual(entry.half_inning, 'TOP')
        self.assertEqual(entry.play_index, 1)

        # Second plate appearance should go to the next slot in the order.
        self._add_play('away', result='K', outs_recorded=1, rbi=0, batter_ending_base='OUT')
        second_entry = ScorecardEntry.objects.filter(scorecard__game=self.game).latest('id')
        self.assertEqual(second_entry.slot.player, self.away_players[1])
        self.assertEqual(second_entry.play_index, 2)

    def test_skip_batter_advances_lineup_without_affecting_batting_totals(self):
        self._set_lineup('away', self.away_players[:2])

        response = self._add_play(
            'away', result='SKIP', outs_recorded=0, rbi=0, batter_ending_base='OUT',
        )

        self.assertEqual(response.status_code, 200)
        skipped_entry = ScorecardEntry.objects.get(scorecard__game=self.game)
        self.assertEqual(skipped_entry.slot.player, self.away_players[0])
        self.assertEqual(skipped_entry.result, 'SKIP')
        self.assertEqual(skipped_entry.outs_recorded, 0)

        self._add_play('away', result='1B', outs_recorded=0, rbi=0, batter_ending_base='1B')
        played_entry = ScorecardEntry.objects.filter(scorecard__game=self.game).latest('id')
        self.assertEqual(played_entry.slot.player, self.away_players[1])

        self.client.post(reverse('game_entry:finalize', args=[self.game.id]))
        self.assertFalse(BattingStatLine.objects.filter(player=self.away_players[0], game=self.game).exists())
        line = BattingStatLine.objects.get(player=self.away_players[1], game=self.game)
        self.assertEqual(line.at_bats, 1)
        self.assertEqual(line.hits, 1)

    def test_double_play_records_two_outs(self):
        self._set_lineup('away', self.away_players[:2])

        response = self._add_play('away', result='DP', outs_recorded=2, batter_ending_base='OUT')

        self.assertEqual(response.status_code, 200)
        entry = ScorecardEntry.objects.get(scorecard__game=self.game)
        self.assertEqual(entry.result, 'DP')
        self.assertEqual(entry.outs_recorded, 2)

    def test_double_play_suggests_two_outs(self):
        suggestion = services.suggest_outcome('DP', (None, None, None))

        self.assertEqual(suggestion['outs_recorded'], 2)
        self.assertEqual(suggestion['batter_ending_base'], 'OUT')

    def test_runner_advancement_and_finalize_credits_runs_rbi_and_hits(self):
        self._set_lineup('away', self.away_players[:2])

        # Player 1 singles; bases empty before, so no runner fields needed.
        self._add_play('away', result='1B', outs_recorded=0, rbi=0, batter_ending_base='1B')

        # Player 2 homers, driving in the runner on 1st and scoring himself.
        self._add_play(
            'away', result='HR', outs_recorded=0, rbi=2,
            batter_ending_base='HOME', runner_1st_ending='HOME',
        )

        finalize_url = reverse('game_entry:finalize', args=[self.game.id])
        response = self.client.post(finalize_url)
        self.assertEqual(response.status_code, 302)

        self.game.refresh_from_db()
        self.assertEqual(self.game.status, 'F')

        result = GameResult.objects.get(game=self.game)
        self.assertEqual(result.away_score, 2)
        self.assertEqual(result.home_score, 0)
        self.assertEqual(result.away_hits, 2)
        self.assertEqual(result.innings_played, 1)
        inning_one = result.innings.get(inning=1)
        self.assertEqual(inning_one.away_runs, 2)
        self.assertEqual(inning_one.home_runs, 0)

        line1 = BattingStatLine.objects.get(player=self.away_players[0], game=self.game)
        self.assertEqual(line1.at_bats, 1)
        self.assertEqual(line1.hits, 1)
        self.assertEqual(line1.singles, 1)
        self.assertEqual(line1.runs, 1)
        self.assertEqual(line1.rbis, 0)

        line2 = BattingStatLine.objects.get(player=self.away_players[1], game=self.game)
        self.assertEqual(line2.at_bats, 1)
        self.assertEqual(line2.home_runs, 1)
        self.assertEqual(line2.runs, 1)
        self.assertEqual(line2.rbis, 2)

    def test_finalize_is_idempotent(self):
        self._set_lineup('away', self.away_players[:1])
        self._add_play('away', result='HR', outs_recorded=0, rbi=1, batter_ending_base='HOME')

        finalize_url = reverse('game_entry:finalize', args=[self.game.id])
        self.client.post(finalize_url)
        self.client.post(finalize_url)

        self.assertEqual(BattingStatLine.objects.filter(game=self.game).count(), 1)
        line = BattingStatLine.objects.get(player=self.away_players[0], game=self.game)
        self.assertEqual(line.home_runs, 1)
        self.assertEqual(line.runs, 1)

    def test_only_last_play_in_half_inning_can_be_deleted(self):
        self._set_lineup('away', self.away_players[:2])
        self._add_play('away', result='1B', outs_recorded=0, rbi=0, batter_ending_base='1B')
        self._add_play('away', result='K', outs_recorded=1, rbi=0, batter_ending_base='OUT')

        first_entry, second_entry = ScorecardEntry.objects.filter(scorecard__game=self.game).order_by('play_index')

        delete_first_url = reverse('game_entry:delete_play', args=[self.game.id, first_entry.id])
        self.client.post(delete_first_url)
        self.assertTrue(ScorecardEntry.objects.filter(id=first_entry.id).exists())

        delete_second_url = reverse('game_entry:delete_play', args=[self.game.id, second_entry.id])
        self.client.post(delete_second_url)
        self.assertFalse(ScorecardEntry.objects.filter(id=second_entry.id).exists())

    def test_finalized_game_blocks_lineup_and_play_edits(self):
        self._set_lineup('away', self.away_players[:1])
        self._add_play('away', result='OUT', outs_recorded=1, rbi=0, batter_ending_base='OUT')

        finalize_url = reverse('game_entry:finalize', args=[self.game.id])
        self.client.post(finalize_url)

        response = self._add_play('away', result='1B', outs_recorded=0, rbi=0, batter_ending_base='1B')
        self.assertContains(response, 'Unfinalize the game')
        self.assertEqual(ScorecardEntry.objects.filter(scorecard__game=self.game).count(), 1)

    def test_unfinalize_allows_editing_again(self):
        self._set_lineup('away', self.away_players[:1])
        self._add_play('away', result='OUT', outs_recorded=1, rbi=0, batter_ending_base='OUT')

        finalize_url = reverse('game_entry:finalize', args=[self.game.id])
        self.client.post(finalize_url)

        unfinalize_url = reverse('game_entry:unfinalize', args=[self.game.id])
        self.client.post(unfinalize_url)

        scorecard = GameScorecard.objects.get(game=self.game)
        self.assertFalse(scorecard.is_finalized)

        response = self._add_play('away', result='K', outs_recorded=1, rbi=0, batter_ending_base='OUT')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ScorecardEntry.objects.filter(scorecard__game=self.game).count(), 2)

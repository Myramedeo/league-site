from unittest.mock import Mock

from django.test import RequestFactory, TestCase
from django.template.loader import render_to_string
from django.urls import reverse

from games.models import Game
from stats.models import BattingStatLine

from players.admin import merge_selected_players
from players.models import LegacyPlayerIdentity, Player, PlayerMergeAudit, Roster
from players.services import find_duplicate_players, merge_players, undo_player_merge
from teams.models import Competition, Season, Team


class PlayerDetailTests(TestCase):
	def setUp(self):
		self.player = Player.objects.create(first_name='Test', last_name='Player')
		self.team = Team.objects.create(name='Test Team')
		self.older_season = Season.objects.create(year=2025)
		self.newer_season = Season.objects.create(year=2026)
		self.older_competition = Competition.objects.create(name='2025 Regular Season', season=self.older_season)
		self.newer_competition = Competition.objects.create(name='2026 Regular Season', season=self.newer_season)

	def create_stat_line(self, season, competition, **stats):
		game = Game.objects.create(
			season=season,
			competition=competition,
			home_team=self.team,
			away_team=Team.objects.create(name=f'Away {season.year}'),
			date=f'{season.year}-06-01',
		)
		return BattingStatLine.objects.create(player=self.player, game=game, **stats)

	def test_player_detail_groups_stats_by_competition_and_adds_overall_row(self):
		self.create_stat_line(self.older_season, self.older_competition, at_bats=10, hits=3, singles=2, doubles=1, rbis=2)
		self.create_stat_line(self.newer_season, self.newer_competition, at_bats=20, hits=10, singles=8, doubles=2, rbis=4)

		response = self.client.get(reverse('player_detail', args=[self.player.id]))

		stats = response.context['batting_stats']
		self.assertEqual(
			[row['competition'] for row in stats],
			['2026 Regular Season', '2025 Regular Season', 'Overall'],
		)
		self.assertEqual(stats[-1]['at_bats'], 30)
		self.assertEqual(stats[-1]['hits'], 13)
		self.assertEqual(stats[-1]['batting_average'], 13 / 30)
		self.assertContains(response, 'Batting Statistics')
		self.assertContains(response, 'Overall')


class PlayerMergeTests(TestCase):
	def test_merge_confirmation_submits_the_target_player(self):
		target = Player.objects.create(first_name='Zoe', last_name='Young')
		source = Player.objects.create(first_name='Amy', last_name='Adams')

		rendered = render_to_string(
			'admin/players/confirm_merge.html',
			{
				'players': [source, target],
				'target': source,
				'opts': Player._meta,
				'cancel_url': reverse('admin:players_player_changelist'),
			},
		)

		form_start = rendered.index('<form')
		form_end = rendered.index('</form>')
		target_input = rendered.index(f'name="target_player_id" value="{target.pk}"')
		self.assertGreater(target_input, form_start)
		self.assertLess(target_input, form_end)

	def test_admin_merge_keeps_the_selected_target_player(self):
		target = Player.objects.create(first_name='Zoe', last_name='Young')
		source = Player.objects.create(first_name='Amy', last_name='Adams')
		request = RequestFactory().post(
			reverse('admin:players_player_changelist'),
			{
				'confirm_merge': '1',
				'target_player_id': str(target.pk),
			},
		)
		request.user = None
		modeladmin = Mock()
		modeladmin.model = Player

		merge_selected_players(modeladmin, request, Player.objects.filter(pk__in=[target.pk, source.pk]))

		self.assertTrue(Player.objects.filter(pk=target.pk, first_name='Zoe').exists())
		self.assertFalse(Player.objects.filter(pk=source.pk).exists())
		self.assertEqual(PlayerMergeAudit.objects.get().target_player_id, target.pk)

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
		self.assertEqual(PlayerMergeAudit.objects.count(), 1)

	def test_undo_merge_restores_original_records(self):
		season = Season.objects.create(year=2026)
		target = Player.objects.create(first_name='John', last_name='Smith')
		source = Player.objects.create(first_name='Johnny', last_name='Smith')
		source_id = source.pk
		team = Team.objects.create(name='Hawks')
		other_team = Team.objects.create(name='Owls')
		Roster.objects.create(player=target, team=team, season=season)
		Roster.objects.create(player=source, team=other_team, season=season)
		identity = LegacyPlayerIdentity.objects.create(
			legacy_player_id=202,
			player=source,
			source_first_name='Johnny',
			source_last_name='Smith',
		)
		game = Game.objects.create(season=season, home_team=team, away_team=other_team, date='2026-06-01')
		BattingStatLine.objects.create(
			player=source,
			game=game,
			at_bats=3,
			hits=1,
			singles=1,
		)

		merge_players(target, source)
		audit = PlayerMergeAudit.objects.get()
		undo_player_merge(audit)

		self.assertTrue(Player.objects.filter(pk=target.pk, first_name='John').exists())
		self.assertTrue(Player.objects.filter(pk=source_id, first_name='Johnny').exists())
		self.assertTrue(Roster.objects.filter(player_id=source_id, team=other_team, season=season).exists())
		self.assertTrue(BattingStatLine.objects.filter(player_id=source_id, game=game, at_bats=3).exists())
		self.assertEqual(LegacyPlayerIdentity.objects.get(pk=identity.pk).player_id, source_id)
		self.assertIsNotNone(PlayerMergeAudit.objects.get(pk=audit.pk).undone_at)

	def test_undo_merge_refuses_changed_data(self):
		target = Player.objects.create(first_name='John', last_name='Smith')
		source = Player.objects.create(first_name='Johnny', last_name='Smith')

		merge_players(target, source)
		audit = PlayerMergeAudit.objects.get()
		Player.objects.filter(pk=target.pk).update(last_name='Changed')

		with self.assertRaisesMessage(ValueError, 'data has changed'):
			undo_player_merge(audit)

		self.assertFalse(Player.objects.filter(pk=source.pk).exists())

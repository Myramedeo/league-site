from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from datetime import date
from unittest.mock import patch

from announcements.models import Announcement
from .models import Article
from games.models import Game, GameResult
from teams.models import Season, Team


class HomePageTests(TestCase):
    def test_homepage_renders_without_template_errors(self):
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/home.html')
        self.assertContains(response, 'Announcements')
        self.assertContains(response, 'No announcements yet')
        self.assertContains(response, 'No season selected')
        self.assertNotContains(response, 'Admin panel')

    def test_homepage_shows_admin_link_to_logged_in_users(self):
        user = get_user_model().objects.create_user(
            username='league-admin',
            password='test-password',
        )
        self.client.force_login(user)

        response = self.client.get(reverse('home'))

        self.assertContains(response, 'Admin Panel')
        self.assertContains(response, reverse('admin:index'))

    @patch('core.views.timezone.localdate', return_value=date(2026, 6, 15))
    def test_homepage_provides_date_aware_games(self, localdate):
        season = Season.objects.create(year=2026)
        hawks = Team.objects.create(name='Hawks')
        bears = Team.objects.create(name='Bears')
        lions = Team.objects.create(name='Lions')
        upcoming_game = Game.objects.create(
            season=season,
            home_team=hawks,
            away_team=bears,
            date=date(2026, 6, 20),
        )
        old_upcoming_game = Game.objects.create(
            season=season,
            home_team=hawks,
            away_team=lions,
            date=date(2026, 6, 10),
        )
        recent_game = Game.objects.create(
            season=season,
            home_team=lions,
            away_team=hawks,
            date=date(2026, 6, 14),
            status='F',
        )
        GameResult.objects.create(
            game=recent_game,
            final_home_score=4,
            final_away_score=3,
        )
        Game.objects.create(
            season=season,
            home_team=bears,
            away_team=lions,
            date=date(2026, 6, 13),
            status='PPD',
        )

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['upcoming_games']), [upcoming_game])
        self.assertEqual(list(response.context['recent_games']), [recent_game])
        self.assertNotIn(old_upcoming_game, response.context['upcoming_games'])
        self.assertContains(response, 'Upcoming')
        self.assertContains(response, 'Recent Results')
        self.assertContains(response, 'Bears')
        self.assertContains(response, '3-4')

    @patch('core.views.compute_standings')
    def test_homepage_renders_announcements_and_compact_standings(self, compute_standings):
        Season.objects.create(year=2026)
        Announcement.objects.create(
            title='Opening Day',
            description='The season begins this weekend.',
        )
        Announcement.objects.create(
            title='Rain Delay',
            description='Tonight\'s game has been postponed.',
        )
        compute_standings.return_value = [{
            'team': 'Hawks',
            'wins': 7,
            'losses': 2,
            'ties': 1,
        }]

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Opening Day')
        self.assertContains(response, 'The season begins this weekend.')
        self.assertContains(response, 'Rain Delay')
        self.assertLess(
            response.content.find(b'Rain Delay'),
            response.content.find(b'Opening Day'),
        )
        self.assertContains(response, '2026 Season')
        self.assertContains(response, 'Hawks')
        self.assertContains(response, '7-2-1')
        for label in ['Teams', 'Standings', 'Stats', 'Schedule']:
            self.assertContains(response, label)
        self.assertContains(response, reverse('standings'))


class ArticlePageTests(TestCase):
    def setUp(self):
        self.article = Article.objects.create(
            legacy_article_id=1,
            title='League News',
            content='<p>Hello <strong>league</strong>.</p>',
        )

    def test_article_list_renders_published_articles(self):
        response = self.client.get(reverse('article_list'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/article_list.html')
        self.assertContains(response, 'League News')

    def test_article_detail_renders_sanitized_content(self):
        response = self.client.get(reverse('article_detail', args=[self.article.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/article.html')
        self.assertContains(response, 'League News')
        self.assertContains(response, '<strong>league</strong>', html=False)

    def test_unknown_slug_returns_404(self):
        response = self.client.get(reverse('article_detail', args=['does-not-exist']))

        self.assertEqual(response.status_code, 404)

from django.test import TestCase
from django.urls import reverse

from .models import Article


class HomePageTests(TestCase):
    def test_homepage_renders_without_template_errors(self):
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/home.html')
        self.assertContains(response, 'Welcome to')
        self.assertContains(response, 'Current Season')


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

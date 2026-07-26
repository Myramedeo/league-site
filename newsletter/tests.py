from django.test import TestCase
from django.urls import reverse
from django.test import override_settings
from unittest.mock import Mock, patch
from uuid import uuid4

from .models import NewsletterSubscriber
from .services import enqueue_resend_welcome_email


class NewsletterSubscriberModelTests(TestCase):
    def test_string_representation(self):
        subscriber = NewsletterSubscriber.objects.create(email='fan@example.com')
        self.assertEqual(str(subscriber), 'fan@example.com')


class NewsletterSignupViewTests(TestCase):
    def test_signup_creates_subscriber(self):
        response = self.client.post(
            reverse('newsletter_signup'),
            {'email': 'newfan@example.com', 'next': reverse('home')},
            follow=True,
        )

        self.assertRedirects(response, reverse('home'))
        self.assertTrue(
            NewsletterSubscriber.objects.filter(email='newfan@example.com', is_active=False).exists()
        )
        subscriber = NewsletterSubscriber.objects.get(email='newfan@example.com')
        self.assertIsNone(subscriber.confirmed_at)

    def test_signup_with_existing_active_email_keeps_single_row(self):
        NewsletterSubscriber.objects.create(email='fan@example.com', is_active=True)

        self.client.post(reverse('newsletter_signup'), {'email': 'fan@example.com'})

        self.assertEqual(NewsletterSubscriber.objects.filter(email='fan@example.com').count(), 1)

    def test_signup_reactivates_inactive_subscriber(self):
        subscriber = NewsletterSubscriber.objects.create(email='inactive@example.com', is_active=False)
        old_token = subscriber.confirmation_token

        self.client.post(reverse('newsletter_signup'), {'email': 'inactive@example.com'})

        subscriber = NewsletterSubscriber.objects.get(email='inactive@example.com')
        self.assertFalse(subscriber.is_active)
        self.assertNotEqual(old_token, subscriber.confirmation_token)

    def test_confirm_activates_subscriber(self):
        subscriber = NewsletterSubscriber.objects.create(email='confirmme@example.com', is_active=False)

        response = self.client.get(reverse('newsletter_confirm', args=[subscriber.confirmation_token]))

        self.assertRedirects(response, reverse('home'))
        subscriber.refresh_from_db()
        self.assertTrue(subscriber.is_active)
        self.assertIsNotNone(subscriber.confirmed_at)

    def test_unsubscribe_deactivates_subscriber(self):
        subscriber = NewsletterSubscriber.objects.create(email='active@example.com', is_active=True)

        response = self.client.get(reverse('newsletter_unsubscribe', args=[subscriber.unsubscribe_token]))

        self.assertRedirects(response, reverse('home'))
        subscriber.refresh_from_db()
        self.assertFalse(subscriber.is_active)

    def test_confirm_unknown_token_returns_404(self):
        response = self.client.get(reverse('newsletter_confirm', args=[uuid4()]))
        self.assertEqual(response.status_code, 404)

    def test_unsubscribe_unknown_token_returns_404(self):
        response = self.client.get(reverse('newsletter_unsubscribe', args=[uuid4()]))
        self.assertEqual(response.status_code, 404)

    def test_invalid_email_does_not_create_subscriber(self):
        self.client.post(reverse('newsletter_signup'), {'email': 'not-an-email'})

        self.assertFalse(NewsletterSubscriber.objects.filter(email='not-an-email').exists())

    def test_get_request_not_allowed(self):
        response = self.client.get(reverse('newsletter_signup'))
        self.assertEqual(response.status_code, 405)


class NewsletterServiceTests(TestCase):
    @override_settings(
        NEWSLETTER_SEND_WELCOME_EMAIL=True,
        RESEND_API_KEY='',
        RESEND_FROM_EMAIL='',
        RESEND_REPLY_TO='',
    )
    def test_enqueue_skips_if_resend_is_not_configured(self):
        subscriber = NewsletterSubscriber.objects.create(email='nosend@example.com')
        fake_resend = Mock()
        fake_resend.Emails.send = Mock()

        with patch('newsletter.services._get_resend_module', return_value=fake_resend):
            with self.captureOnCommitCallbacks(execute=True):
                enqueue_resend_welcome_email(subscriber)

        fake_resend.Emails.send.assert_not_called()

    @override_settings(
        NEWSLETTER_SEND_WELCOME_EMAIL=False,
        RESEND_API_KEY='re_test_key',
        RESEND_FROM_EMAIL='updates@example.com',
        RESEND_REPLY_TO='reply@example.com',
    )
    def test_enqueue_skips_if_welcome_sending_is_disabled(self):
        subscriber = NewsletterSubscriber.objects.create(email='disabled@example.com')
        fake_resend = Mock()
        fake_resend.Emails.send = Mock()

        with patch('newsletter.services._get_resend_module', return_value=fake_resend):
            with self.captureOnCommitCallbacks(execute=True):
                enqueue_resend_welcome_email(subscriber)

        fake_resend.Emails.send.assert_not_called()

    @override_settings(
        NEWSLETTER_SEND_WELCOME_EMAIL=True,
        RESEND_API_KEY='re_test_key',
        RESEND_FROM_EMAIL='updates@example.com',
        RESEND_REPLY_TO='reply@example.com',
        SITE_BASE_URL='https://example.test',
    )
    def test_enqueue_sends_welcome_email_after_commit(self):
        subscriber = NewsletterSubscriber.objects.create(email='fan@example.com')
        fake_resend = Mock()
        fake_resend.Emails.send = Mock()

        with patch('newsletter.services._get_resend_module', return_value=fake_resend):
            with self.captureOnCommitCallbacks(execute=True):
                enqueue_resend_welcome_email(subscriber)

        fake_resend.Emails.send.assert_called_once()
        payload = fake_resend.Emails.send.call_args.args[0]
        self.assertEqual(payload['from'], 'updates@example.com')
        self.assertEqual(payload['to'], ['fan@example.com'])
        self.assertEqual(payload['reply_to'], 'reply@example.com')
        self.assertIn('newsletter/confirm/', payload['text'])
        self.assertIn(str(subscriber.confirmation_token), payload['text'])
        self.assertIn('newsletter/unsubscribe/', payload['text'])
        self.assertIn(str(subscriber.unsubscribe_token), payload['text'])

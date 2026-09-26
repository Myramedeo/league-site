import logging
from importlib import import_module

from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from .models import NewsletterCampaign, NewsletterSubscriber


logger = logging.getLogger(__name__)

RESEND_BATCH_LIMIT = 100


def _get_resend_module():
    try:
        return import_module('resend')
    except ModuleNotFoundError:
        logger.warning('Skipping newsletter welcome email: resend package is not installed.')
        return None


def _send_resend_welcome_email(subscriber):
    if not settings.NEWSLETTER_SEND_WELCOME_EMAIL:
        return

    if not settings.RESEND_API_KEY or not settings.RESEND_FROM_EMAIL:
        logger.warning(
            'Skipping newsletter welcome email: RESEND_API_KEY or RESEND_FROM_EMAIL is not configured.'
        )
        return

    resend_module = _get_resend_module()
    if resend_module is None:
        return

    resend_module.api_key = settings.RESEND_API_KEY

    confirm_url = (
        f"{settings.SITE_BASE_URL.rstrip('/')}"
        f"{reverse('newsletter_confirm', args=[subscriber.confirmation_token])}"
    )
    unsubscribe_url = (
        f"{settings.SITE_BASE_URL.rstrip('/')}"
        f"{reverse('newsletter_unsubscribe', args=[subscriber.unsubscribe_token])}"
    )

    payload = {
        'from': settings.RESEND_FROM_EMAIL,
        'to': [subscriber.email],
        'subject': 'Confirm your HOBO 55+ League subscription',
        'html': (
            '<p>Thanks for subscribing to Hamilton Oldtimers Baseball Organization 55+ Division updates.</p>'
            f'<p>Please confirm your subscription: <a href="{confirm_url}">{confirm_url}</a></p>'
            f'<p>If this was not you, unsubscribe immediately: <a href="{unsubscribe_url}">{unsubscribe_url}</a></p>'
        ),
        'text': (
            'Thanks for subscribing to HOBO 55+ League updates.\n\n'
            f'Confirm your subscription: {confirm_url}\n\n'
            f'If this was not you, unsubscribe immediately: {unsubscribe_url}'
        ),
    }
    if settings.RESEND_REPLY_TO:
        payload['reply_to'] = settings.RESEND_REPLY_TO

    try:
        resend_module.Emails.send(payload)
    except Exception:
        logger.exception('Resend welcome email failed for subscriber id=%s', subscriber.id)


def enqueue_resend_welcome_email(subscriber):
    """Queue confirmation email to send after database commit."""
    transaction.on_commit(lambda: _send_resend_welcome_email(subscriber))


def get_campaign_recipients():
    """Subscribers eligible for newsletter broadcasts."""
    return NewsletterSubscriber.objects.filter(is_active=True, confirmed_at__isnull=False)


def send_newsletter_campaign(campaign, dry_run=False):
    """Send a NewsletterCampaign to all confirmed subscribers via Resend batch send.

    Raises RuntimeError instead of sending if already sent, Resend isn't configured,
    or the resend package is missing, so callers can surface a clear error.
    """
    if campaign.status == NewsletterCampaign.STATUS_SENT:
        raise RuntimeError(f'Campaign "{campaign.subject}" has already been sent.')

    if not campaign.text_body and not campaign.html_body:
        raise RuntimeError('Campaign has neither a text body nor an HTML body.')

    if not settings.RESEND_API_KEY or not settings.RESEND_FROM_EMAIL:
        raise RuntimeError('RESEND_API_KEY or RESEND_FROM_EMAIL is not configured.')

    resend_module = _get_resend_module()
    if resend_module is None:
        raise RuntimeError('The resend package is not installed.')

    recipients = list(get_campaign_recipients())

    if dry_run:
        return len(recipients)

    resend_module.api_key = settings.RESEND_API_KEY

    def _build_email(subscriber):
        unsubscribe_url = (
            f"{settings.SITE_BASE_URL.rstrip('/')}"
            f"{reverse('newsletter_unsubscribe', args=[subscriber.unsubscribe_token])}"
        )
        email = {
            'from': settings.RESEND_FROM_EMAIL,
            'to': [subscriber.email],
            'subject': campaign.subject,
            'headers': {'List-Unsubscribe': f'<{unsubscribe_url}>'},
        }
        if campaign.html_body:
            email['html'] = campaign.html_body
        if campaign.text_body:
            email['text'] = campaign.text_body
        if settings.RESEND_REPLY_TO:
            email['reply_to'] = settings.RESEND_REPLY_TO
        return email

    campaign.status = NewsletterCampaign.STATUS_SENDING
    campaign.save(update_fields=['status', 'updated_at'])

    try:
        for i in range(0, len(recipients), RESEND_BATCH_LIMIT):
            batch = [_build_email(s) for s in recipients[i:i + RESEND_BATCH_LIMIT]]
            resend_module.Batch.send(batch)
    except Exception as exc:
        campaign.status = NewsletterCampaign.STATUS_FAILED
        campaign.error_message = str(exc)
        campaign.save(update_fields=['status', 'error_message', 'updated_at'])
        logger.exception('Newsletter campaign send failed for campaign id=%s', campaign.id)
        raise

    campaign.status = NewsletterCampaign.STATUS_SENT
    campaign.recipient_count = len(recipients)
    campaign.sent_at = timezone.now()
    campaign.error_message = ''
    campaign.save(update_fields=['status', 'recipient_count', 'sent_at', 'error_message', 'updated_at'])
    return len(recipients)

import logging
from importlib import import_module

from django.conf import settings
from django.db import transaction
from django.urls import reverse


logger = logging.getLogger(__name__)


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

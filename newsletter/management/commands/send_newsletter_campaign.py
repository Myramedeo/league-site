from django.core.management.base import BaseCommand, CommandError

from newsletter.models import NewsletterCampaign
from newsletter.services import get_campaign_recipients, send_newsletter_campaign


class Command(BaseCommand):
    help = 'Send a NewsletterCampaign to all confirmed subscribers via Resend.'

    def add_arguments(self, parser):
        parser.add_argument('campaign_id', type=int)
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report the recipient count without sending any email.',
        )
        parser.add_argument(
            '--yes',
            action='store_true',
            help='Skip the confirmation prompt (required for a real send).',
        )

    def handle(self, *args, **options):
        try:
            campaign = NewsletterCampaign.objects.get(pk=options['campaign_id'])
        except NewsletterCampaign.DoesNotExist as exc:
            raise CommandError(f"No campaign with id={options['campaign_id']}") from exc

        if options['dry_run']:
            count = get_campaign_recipients().count()
            self.stdout.write(f'[dry run] "{campaign.subject}" would be sent to {count} subscriber(s).')
            return

        if not options['yes']:
            raise CommandError('Pass --yes to confirm a real send (or --dry-run to preview).')

        try:
            count = send_newsletter_campaign(campaign, dry_run=False)
        except RuntimeError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(f'Sent "{campaign.subject}" to {count} subscriber(s).'))

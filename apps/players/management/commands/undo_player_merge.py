from django.core.management.base import BaseCommand, CommandError

from players.models import PlayerMergeAudit
from players.services import undo_player_merge


class Command(BaseCommand):
    help = 'Undo a player merge using its audit record.'

    def add_arguments(self, parser):
        parser.add_argument('audit_id', type=int, help='Player merge audit ID.')

    def handle(self, *args, **options):
        try:
            audit = PlayerMergeAudit.objects.get(pk=options['audit_id'])
        except PlayerMergeAudit.DoesNotExist:
            raise CommandError(f'Merge audit {options["audit_id"]} does not exist.')

        try:
            undo_player_merge(audit)
        except ValueError as error:
            raise CommandError(str(error))

        self.stdout.write(self.style.SUCCESS(f'Undid player merge audit {audit.pk}.'))
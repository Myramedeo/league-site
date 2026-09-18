from django.core.management.base import BaseCommand, CommandError

from players.models import Player
from players.services import merge_players


class Command(BaseCommand):
    help = 'Merge one player record into another, preserving and consolidating related data.'

    def add_arguments(self, parser):
        parser.add_argument('--target-id', type=int, required=True, help='Primary player ID to keep.')
        parser.add_argument('--source-id', type=int, required=True, help='Duplicate player ID to merge into the target.')
        parser.add_argument('--dry-run', action='store_true', help='Preview the merge without deleting the source player.')

    def handle(self, *args, **options):
        target_id = options['target_id']
        source_id = options['source_id']

        try:
            target_player = Player.objects.get(pk=target_id)
        except Player.DoesNotExist:
            raise CommandError(f'Player with id {target_id} does not exist.')

        try:
            source_player = Player.objects.get(pk=source_id)
        except Player.DoesNotExist:
            raise CommandError(f'Player with id {source_id} does not exist.')

        if target_player.pk == source_player.pk:
            raise CommandError('Target and source player cannot be the same record.')

        if options['dry_run']:
            self.stdout.write(self.style.WARNING(
                f'Dry run: would merge {source_player} into {target_player}.'
            ))
            return

        merged = merge_players(target_player, source_player)
        self.stdout.write(self.style.SUCCESS(
            f'Merged {source_player} into {merged}.'
        ))

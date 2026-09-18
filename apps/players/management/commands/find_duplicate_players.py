from django.core.management.base import BaseCommand

from players.services import find_duplicate_players


class Command(BaseCommand):
    help = 'Find likely duplicate player records based on similar names.'

    def add_arguments(self, parser):
        parser.add_argument('--threshold', type=float, default=0.8, help='Similarity cutoff between 0 and 1 (default: 0.8).')

    def handle(self, *args, **options):
        matches = find_duplicate_players(threshold=float(options['threshold']))

        if not matches:
            self.stdout.write(self.style.WARNING('No likely duplicate players found.'))
            return

        for match in matches:
            left = match['left']
            right = match['right']
            self.stdout.write(
                f'{left.last_name}, {left.first_name} | {right.last_name}, {right.first_name} | score={match["score"]:.3f}'
            )

        self.stdout.write(self.style.SUCCESS(f'Found {len(matches)} likely duplicate pair(s).'))

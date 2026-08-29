import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.imports.legacy_csv import read_csv_file, validate_source, ImportReport, _parse_score
from games.models import Game, GameResult, InningScore
from players.models import LegacyPlayerIdentity, Player, Roster
from stats.models import BattingStatLine
from teams.models import Competition, LegacyTeamIdentity, Season, Team


PLACEHOLDER_TEAMS = {
    'extra date', 'if needed', 'higher seeded semi-final winner',
    'lower seeded semi-final winner', 'tbd', 'off day',
}


def canonical_team_name(name):
    name = name.strip()
    if name in {"A's", 'Athletics'}:
        return "A's"
    return name


def parse_division_name(name):
    match = re.search(r'\b(\d{4})\b', name)
    if not match:
        return None, 'OTHER'
    phase = 'PLAYOFFS' if 'playoff' in name.lower() else 'REGULAR'
    return int(match.group(1)), phase


def parse_boolean(value):
    return str(value).strip().lower() in {'true', '1', 'yes', 'y'}


def load_rows(source_dir, report):
    return {
        filename: read_csv_file(source_dir, filename, report)
        for filename in ('divisions.csv', 'teams.csv', 'players.csv', 'game_ids.csv',
                         'game_metadata.csv', 'innings.csv', 'batting.csv')
    }


def rows_by(rows, field):
    return {row.get(field): row for _, row in rows}


class Command(BaseCommand):
    help = 'Import legacy baseball CSV files into the Django database.'

    def add_arguments(self, parser):
        parser.add_argument('source_dir')
        parser.add_argument('--dry-run', action='store_true', help='Validate without writing database records.')
        parser.add_argument('--strict', action='store_true', help='Fail when validation errors are found.')
        parser.add_argument('--division-id', type=int, help='Import only one legacy division.')

    def handle(self, *args, **options):
        report = validate_source(options['source_dir'])
        if report.errors:
            self._print_report(report)
            raise CommandError(f'Legacy CSV validation failed with {len(report.errors)} error(s).')

        if options['dry_run']:
            self._print_report(report)
            self.stdout.write(self.style.SUCCESS('Legacy CSV validation completed.'))
            return

        rows = load_rows(options['source_dir'], ImportReport())
        with transaction.atomic():
            self.import_rows(rows, report, options['division_id'])

        self._print_report(report)
        self.stdout.write(self.style.SUCCESS('Legacy CSV import completed.'))

    def _print_report(self, report):
        for filename, count in report.counts.items():
            self.stdout.write(f'{filename}: {count} rows')
        for diagnostic in report.diagnostics:
            stream = self.stderr if diagnostic.level == 'ERROR' else self.stdout
            stream.write(str(diagnostic))

    def import_rows(self, rows, report, division_id=None):
        divisions = rows['divisions.csv']
        if division_id is not None:
            divisions = [(number, row) for number, row in divisions
                         if int(row['Division ID']) == division_id]
            if not divisions:
                raise CommandError(f'Unknown legacy Division ID {division_id}.')

        competitions = {}
        for row_number, row in divisions:
            source_id = int(row['Division ID'])
            year, phase = parse_division_name(row['Division Name'])
            season, _ = Season.objects.get_or_create(year=year, defaults={'name': str(year)})
            competition, created = Competition.objects.update_or_create(
                legacy_division_id=source_id,
                defaults={
                    'season': season,
                    'name': row['Division Name'].strip(),
                    'phase': phase,
                    'source_order': int(row['Order']) if row.get('Order') else None,
                    'expected_team_count': int(row['Teams Assigned']),
                },
            )
            competitions[source_id] = competition
            report.count('competitions_created' if created else 'competitions_updated')

        team_identities = {}
        canonical_teams = {}
        for row_number, row in rows['teams.csv']:
            source_division = int(row['Division ID'])
            if source_division not in competitions:
                continue
            source_name = row['Team Name'].strip()
            if source_name.lower() in PLACEHOLDER_TEAMS:
                report.add('WARNING', 'teams.csv', row_number, f'skipped placeholder team {source_name!r}')
                continue
            name = canonical_team_name(source_name)
            team = canonical_teams.get(name)
            if team is None:
                team, _ = Team.objects.get_or_create(name=name)
                canonical_teams[name] = team
            identity, created = LegacyTeamIdentity.objects.update_or_create(
                legacy_team_id=int(row['Team ID']),
                defaults={'team': team, 'competition': competitions[source_division], 'source_name': source_name},
            )
            team_identities[int(row['Team ID'])] = identity
            report.count('team_identities_created' if created else 'team_identities_updated')

        player_identities = {}
        player_rows = {}
        for row_number, row in rows['players.csv']:
            source_id = int(row['Player ID'])
            player_rows.setdefault(source_id, (row_number, row))
        for source_id, (row_number, row) in player_rows.items():
            number = row.get('Number', '').strip()
            player, _ = Player.objects.get_or_create(
                first_name=row['First Name'].strip(),
                last_name=row['Last Name'].strip(),
                defaults={'jersey_number': int(number) if number.isdigit() else None},
            )
            identity, created = LegacyPlayerIdentity.objects.update_or_create(
                legacy_player_id=source_id,
                defaults={
                    'player': player,
                    'source_first_name': row['First Name'].strip(),
                    'source_last_name': row['Last Name'].strip(),
                },
            )
            player_identities[source_id] = identity
            report.count('player_identities_created' if created else 'player_identities_updated')

        team_names_by_competition = defaultdict(dict)
        for identity in team_identities.values():
            team_names_by_competition[identity.competition_id][canonical_team_name(identity.source_name)] = identity.team

        for row_number, row in rows['players.csv']:
            division_name = row.get('Division', '').strip()
            team_name = row.get('Team', '').strip()
            if not division_name or not team_name:
                continue
            competition = next((item for item in competitions.values() if item.name == division_name), None)
            player_identity = player_identities.get(int(row['Player ID']))
            team = team_names_by_competition.get(competition.id, {}).get(canonical_team_name(team_name)) if competition else None
            if not competition or not team or not player_identity:
                report.add('WARNING', 'players.csv', row_number, 'skipped unresolved roster row')
                continue
            Roster.objects.update_or_create(
                player=player_identity.player,
                team=team,
                season=competition.season,
                competition=competition,
            )
            report.count('rosters_written')

        metadata = rows_by(rows['game_metadata.csv'], 'game_id')
        games_by_source = {}
        for row_number, row in rows['game_ids.csv']:
            source_id = int(row['Game ID'])
            competition = competitions.get(int(row['Division ID']))
            visitors = row['Visitors'].strip()
            home = row['Home'].strip()
            if not competition or visitors.lower() in PLACEHOLDER_TEAMS or home.lower() in PLACEHOLDER_TEAMS:
                continue
            teams = team_names_by_competition[competition.id]
            away_team = teams.get(canonical_team_name(visitors))
            home_team = teams.get(canonical_team_name(home))
            if not away_team or not home_team:
                report.add('WARNING', 'game_ids.csv', row_number, 'skipped game with unresolved team')
                continue
            raw_status = row['Status'].strip()
            status = 'F' if raw_status.startswith('F ') else raw_status[:3].upper()
            if status not in dict(Game.STATUS_CHOICES):
                status = 'TBP'
            game, created = Game.objects.update_or_create(
                legacy_game_id=source_id,
                defaults={
                    'season': competition.season,
                    'competition': competition,
                    'home_team': home_team,
                    'away_team': away_team,
                    'date': datetime.strptime(row['Date'], '%m/%d/%Y').date(),
                    'status': status,
                    'venue': row['Location'].strip() or None,
                    'exclude_from_standings': parse_boolean(metadata.get(str(source_id), {}).get('exclude_from_standings', False)),
                },
            )
            games_by_source[source_id] = game
            report.count('games_created' if created else 'games_updated')
            game_metadata = metadata.get(str(source_id))
            if status == 'F' and game_metadata:
                result, _ = GameResult.objects.update_or_create(
                    game=game,
                    defaults={
                        'final_home_score': int(game_metadata['home_score']),
                        'final_away_score': int(game_metadata['away_score']),
                        'innings_played': int(game_metadata['innings_played']),
                    },
                )
                for _, inning in [item for item in rows['innings.csv'] if int(item[1]['game_id']) == source_id]:
                    InningScore.objects.update_or_create(
                        result=result,
                        inning=int(inning['inning']),
                        defaults={'home_runs': int(inning['home_runs']), 'away_runs': int(inning['away_runs'])},
                    )
                report.count('results_written')

        for row_number, row in rows['batting.csv']:
            game = games_by_source.get(int(row['game_id']))
            player_identity = player_identities.get(int(row['player_id']))
            if not game or not player_identity:
                continue
            hits = sum(int(row[field]) for field in ('single', 'double', 'triple', 'home_run'))
            BattingStatLine.objects.update_or_create(
                game=game,
                player=player_identity.player,
                defaults={
                    'at_bats': int(row['at_bat']), 'runs': int(row['run']), 'hits': hits,
                    'rbis': int(row['runs_batted_in']), 'walks': int(row['walk']),
                    'strikeouts': int(row['strikeout']), 'singles': int(row['single']),
                    'doubles': int(row['double']), 'triples': int(row['triple']),
                    'home_runs': int(row['home_run']), 'hit_by_pitch': int(row.get('hit_by_pitch', 0)),
                    'stolen_bases': int(row.get('stolen_base', 0)), 'sacrifices': int(row.get('sacrifice', 0)),
                    'reached_on_error': int(row.get('roe', 0)),
                },
            )
            report.count('batting_lines_written')
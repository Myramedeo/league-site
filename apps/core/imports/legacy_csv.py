import csv
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


REQUIRED_HEADERS = {
    'divisions.csv': {'Division ID', 'Division Name', 'Teams Assigned'},
    'teams.csv': {'Team ID', 'Team Name', 'Division ID'},
    'players.csv': {'Player ID', 'Last Name', 'First Name', 'Division', 'Team'},
    'game_ids.csv': {'Game ID', 'Date', 'Status', 'Visitors', 'Home', 'Location', 'Division ID'},
    'game_metadata.csv': {'game_id', 'status', 'innings_played', 'exclude_from_standings', 'home_score', 'away_score'},
    'innings.csv': {'game_id', 'inning', 'home_runs', 'away_runs'},
    'batting.csv': {
        'game_id', 'player_id', 'team_type', 'at_bat', 'run', 'single', 'double',
        'triple', 'home_run', 'runs_batted_in', 'walk', 'strikeout',
    },
}


@dataclass
class Diagnostic:
    level: str
    filename: str
    row_number: int | None
    message: str

    def __str__(self):
        location = self.filename
        if self.row_number is not None:
            location += f':{self.row_number}'
        return f'[{self.level}] {location}: {self.message}'


@dataclass
class ImportReport:
    counts: dict[str, int] = field(default_factory=dict)
    diagnostics: list[Diagnostic] = field(default_factory=list)

    def count(self, key, amount=1):
        self.counts[key] = self.counts.get(key, 0) + amount

    def add(self, level, filename, row_number, message):
        self.diagnostics.append(Diagnostic(level, filename, row_number, message))

    @property
    def errors(self):
        return [item for item in self.diagnostics if item.level == 'ERROR']


def _parse_int(value, filename, row_number, field_name, report, allow_blank=False):
    if value in (None, '') and allow_blank:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        report.add('ERROR', filename, row_number, f'{field_name} must be an integer')
        return None
    if parsed < 0:
        report.add('ERROR', filename, row_number, f'{field_name} must not be negative')
    return parsed


def _parse_date(value, filename, row_number, report):
    try:
        return datetime.strptime(value, '%m/%d/%Y').date()
    except (TypeError, ValueError):
        report.add('ERROR', filename, row_number, 'Date must use M/D/YYYY format')
        return None


def _parse_score(status):
    match = re.fullmatch(r'F\s+(\d+)\s*-\s*(\d+)', status.strip())
    if not match:
        return None
    visitors, home = (int(value) for value in match.groups())
    return {'away_score': visitors, 'home_score': home}


def read_csv_file(source_dir, filename, report):
    path = Path(source_dir) / filename
    if not path.exists():
        report.add('ERROR', filename, None, 'file does not exist')
        return []

    try:
        handle = path.open('r', encoding='utf-8-sig', newline='')
    except UnicodeDecodeError:
        report.add('ERROR', filename, None, 'file is not valid UTF-8')
        return []

    with handle:
        reader = csv.DictReader(handle)
        headers = set(reader.fieldnames or [])
        missing = REQUIRED_HEADERS.get(filename, set()) - headers
        if missing:
            report.add('ERROR', filename, 1, f'missing headers: {", ".join(sorted(missing))}')
            return []
        rows = []
        for row_number, row in enumerate(reader, start=2):
            rows.append((row_number, row))
            report.count(filename)
        return rows


def validate_source(source_dir):
    report = ImportReport()
    source = Path(source_dir)
    files = list(REQUIRED_HEADERS)
    rows = {filename: read_csv_file(source, filename, report) for filename in files}

    division_ids = set()
    for row_number, row in rows['divisions.csv']:
        division_id = _parse_int(row.get('Division ID'), 'divisions.csv', row_number, 'Division ID', report)
        _parse_int(row.get('Teams Assigned'), 'divisions.csv', row_number, 'Teams Assigned', report)
        if division_id in division_ids:
            report.add('ERROR', 'divisions.csv', row_number, f'duplicate Division ID {division_id}')
        division_ids.add(division_id)
        if not re.search(r'\b(\d{4})\b', row.get('Division Name', '')):
            report.add('ERROR', 'divisions.csv', row_number, 'Division Name does not contain a four-digit year')

    team_ids = set()
    for row_number, row in rows['teams.csv']:
        team_id = _parse_int(row.get('Team ID'), 'teams.csv', row_number, 'Team ID', report)
        division_id = _parse_int(row.get('Division ID'), 'teams.csv', row_number, 'Division ID', report)
        if division_id not in division_ids:
            report.add('ERROR', 'teams.csv', row_number, f'unknown Division ID {division_id}')
        if team_id in team_ids:
            report.add('ERROR', 'teams.csv', row_number, f'duplicate Team ID {team_id}')
        team_ids.add(team_id)

    player_ids = set()
    for row_number, row in rows['players.csv']:
        player_id = _parse_int(row.get('Player ID'), 'players.csv', row_number, 'Player ID', report)
        if player_id in player_ids:
            report.add('WARNING', 'players.csv', row_number, f'repeated Player ID {player_id}; treat as one source identity')
        player_ids.add(player_id)

    game_ids = set()
    for row_number, row in rows['game_ids.csv']:
        game_id = _parse_int(row.get('Game ID'), 'game_ids.csv', row_number, 'Game ID', report)
        division_id = _parse_int(row.get('Division ID'), 'game_ids.csv', row_number, 'Division ID', report)
        _parse_date(row.get('Date'), 'game_ids.csv', row_number, report)
        if division_id not in division_ids:
            report.add('ERROR', 'game_ids.csv', row_number, f'unknown Division ID {division_id}')
        if game_id in game_ids:
            report.add('ERROR', 'game_ids.csv', row_number, f'duplicate Game ID {game_id}')
        game_ids.add(game_id)
        status = row.get('Status', '').strip()
        if status.startswith('F ') and _parse_score(status) is None:
            report.add('ERROR', 'game_ids.csv', row_number, f'invalid final score status {status!r}')
        if row.get('Visitors', '').strip().lower() in {'off day', 'tbd'} or row.get('Home', '').strip().lower() in {'off day', 'tbd'}:
            report.add('WARNING', 'game_ids.csv', row_number, 'placeholder/off-day fixture will be skipped during import')

    for row_number, row in rows['game_metadata.csv']:
        game_id = _parse_int(row.get('game_id'), 'game_metadata.csv', row_number, 'game_id', report)
        for field_name in ('innings_played', 'home_score', 'away_score'):
            _parse_int(row.get(field_name), 'game_metadata.csv', row_number, field_name, report)
        if game_id not in game_ids:
            report.add('ERROR', 'game_metadata.csv', row_number, f'orphan game_id {game_id}')

    for row_number, row in rows['innings.csv']:
        game_id = _parse_int(row.get('game_id'), 'innings.csv', row_number, 'game_id', report)
        inning = _parse_int(row.get('inning'), 'innings.csv', row_number, 'inning', report)
        for field_name in ('home_runs', 'away_runs'):
            _parse_int(row.get(field_name), 'innings.csv', row_number, field_name, report)
        if inning == 0:
            report.add('ERROR', 'innings.csv', row_number, 'inning must be positive')
        if game_id not in game_ids:
            report.add('ERROR', 'innings.csv', row_number, f'orphan game_id {game_id}')

    for row_number, row in rows['batting.csv']:
        game_id = _parse_int(row.get('game_id'), 'batting.csv', row_number, 'game_id', report)
        player_id = _parse_int(row.get('player_id'), 'batting.csv', row_number, 'player_id', report)
        for field_name in ('at_bat', 'run', 'single', 'double', 'triple', 'home_run', 'runs_batted_in', 'walk', 'strikeout'):
            _parse_int(row.get(field_name), 'batting.csv', row_number, field_name, report)
        if row.get('team_type') not in {'home', 'away'}:
            report.add('ERROR', 'batting.csv', row_number, 'team_type must be home or away')
        if game_id not in game_ids:
            report.add('ERROR', 'batting.csv', row_number, f'orphan game_id {game_id}')
        if player_id not in player_ids:
            report.add('ERROR', 'batting.csv', row_number, f'orphan player_id {player_id}')

    return report
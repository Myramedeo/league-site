from django.db.models import Sum, F, Q
from .models import BattingStatLine, PitchingStatLine


def _batting_totals_row(totals, label):
    at_bats = totals.get('at_bats') or 0
    hits = totals.get('hits') or 0
    walks = totals.get('walks') or 0
    hit_by_pitch = totals.get('hit_by_pitch') or 0
    sacrifices = totals.get('sacrifices') or 0
    singles = totals.get('singles') or 0
    doubles = totals.get('doubles') or 0
    triples = totals.get('triples') or 0
    home_runs = totals.get('home_runs') or 0
    plate_appearances = at_bats + walks + hit_by_pitch + sacrifices
    batting_average = hits / at_bats if at_bats else 0.0
    on_base_percentage = (
        (hits + walks + hit_by_pitch) / plate_appearances
        if plate_appearances else 0.0
    )
    total_bases = singles + (2 * doubles) + (3 * triples) + (4 * home_runs)
    slugging_percentage = total_bases / at_bats if at_bats else 0.0

    return {
        'competition': label,
        'at_bats': at_bats,
        'runs': totals.get('runs') or 0,
        'hits': hits,
        'doubles': doubles,
        'triples': triples,
        'home_runs': home_runs,
        'rbis': totals.get('rbis') or 0,
        'walks': walks,
        'strikeouts': totals.get('strikeouts') or 0,
        'batting_average': batting_average,
        'on_base_percentage': on_base_percentage,
        'slugging_percentage': slugging_percentage,
        'on_base_plus_slugging': on_base_percentage + slugging_percentage,
    }


def player_batting_stats(player):
    """Returns a player's batting totals by competition, followed by career totals."""
    fields = (
        'at_bats', 'runs', 'hits', 'rbis', 'walks', 'strikeouts',
        'hit_by_pitch', 'sacrifices', 'singles', 'doubles', 'triples',
        'home_runs',
    )
    # Rows with no competition assigned (legacy gaps) are excluded here but still count toward Overall.
    competition_rows = (
        BattingStatLine.objects
        .filter(player=player, game__competition__isnull=False)
        .values('game__competition__id', 'game__competition__name', 'game__competition__season__year')
        .annotate(**{field: Sum(field) for field in fields})
        .order_by('-game__competition__season__year', 'game__competition__name')
    )

    results = []
    for row in competition_rows:
        results.append(_batting_totals_row(row, row['game__competition__name']))

    overall_totals = BattingStatLine.objects.filter(player=player).aggregate(
        **{field: Sum(field) for field in fields}
    )
    if results:
        results.append(_batting_totals_row(overall_totals, 'Overall'))

    return results


def team_batting_stats(team, competition):
    """Returns each roster player's competition batting totals for a team, in roster order, zero-filled if no lines recorded."""
    from players.models import Roster

    roster_entries = (
        Roster.objects.filter(team=team, competition=competition, show_in_team_list=True)
        .select_related('player')
        .order_by('player__last_name', 'player__first_name')
    )

    seen_player_ids = set()
    unique_entries = []
    for entry in roster_entries:
        if entry.player_id not in seen_player_ids:
            seen_player_ids.add(entry.player_id)
            unique_entries.append(entry)

    totals_by_player = {
        row['player_id']: row
        for row in (
            BattingStatLine.objects
            .filter(game__competition=competition, player_id__in=seen_player_ids)
            .values('player_id')
            .annotate(
                at_bats=Sum('at_bats'),
                runs=Sum('runs'),
                hits=Sum('hits'),
                rbis=Sum('rbis'),
                walks=Sum('walks'),
                strikeouts=Sum('strikeouts'),
                hit_by_pitch=Sum('hit_by_pitch'),
                sacrifices=Sum('sacrifices'),
                singles=Sum('singles'),
                doubles=Sum('doubles'),
                triples=Sum('triples'),
                home_runs=Sum('home_runs'),
            )
        )
    }

    results = []
    for entry in unique_entries:
        totals = totals_by_player.get(entry.player_id, {})
        at_bats = totals.get('at_bats') or 0
        hits = totals.get('hits') or 0
        walks = totals.get('walks') or 0
        hit_by_pitch = totals.get('hit_by_pitch') or 0
        sacrifices = totals.get('sacrifices') or 0
        singles = totals.get('singles') or 0
        doubles = totals.get('doubles') or 0
        triples = totals.get('triples') or 0
        home_runs = totals.get('home_runs') or 0
        plate_appearances = at_bats + walks + hit_by_pitch + sacrifices
        batting_average = round(hits / at_bats, 3) if at_bats else 0.0
        raw_on_base_percentage = ((hits + walks + hit_by_pitch) / plate_appearances) if plate_appearances else 0.0
        on_base_percentage = round(raw_on_base_percentage, 3)
        total_bases = singles + (2 * doubles) + (3 * triples) + (4 * home_runs)
        raw_slugging_percentage = (total_bases / at_bats) if at_bats else 0.0
        slugging_percentage = round(raw_slugging_percentage, 3)

        results.append({
            'player': entry.player,
            'at_bats': at_bats,
            'runs': totals.get('runs') or 0,
            'hits': hits,
            'doubles': doubles,
            'triples': triples,
            'home_runs': home_runs,
            'rbis': totals.get('rbis') or 0,
            'walks': walks,
            'strikeouts': totals.get('strikeouts') or 0,
            'batting_average': batting_average,
            'on_base_percentage': on_base_percentage,
            'slugging_percentage': slugging_percentage,
            'on_base_plus_slugging': round(raw_on_base_percentage + raw_slugging_percentage, 3),
        })

    return results


def competition_batting_stats(competition):
    """Returns each rostered player's competition batting totals across all teams, zero-filled if no lines recorded."""
    from players.models import Roster

    roster_entries = (
        Roster.objects.filter(competition=competition, show_in_team_list=True)
        .select_related('player')
        .order_by('player__last_name', 'player__first_name')
    )

    seen_player_ids = set()
    unique_entries = []
    for entry in roster_entries:
        if entry.player_id not in seen_player_ids:
            seen_player_ids.add(entry.player_id)
            unique_entries.append(entry)

    totals_by_player = {
        row['player_id']: row
        for row in (
            BattingStatLine.objects
            .filter(game__competition=competition, player_id__in=seen_player_ids)
            .values('player_id')
            .annotate(
                at_bats=Sum('at_bats'),
                runs=Sum('runs'),
                hits=Sum('hits'),
                rbis=Sum('rbis'),
                walks=Sum('walks'),
                strikeouts=Sum('strikeouts'),
                hit_by_pitch=Sum('hit_by_pitch'),
                sacrifices=Sum('sacrifices'),
                singles=Sum('singles'),
                doubles=Sum('doubles'),
                triples=Sum('triples'),
                home_runs=Sum('home_runs'),
            )
        )
    }

    results = []
    for entry in unique_entries:
        totals = totals_by_player.get(entry.player_id, {})
        at_bats = totals.get('at_bats') or 0
        hits = totals.get('hits') or 0
        walks = totals.get('walks') or 0
        hit_by_pitch = totals.get('hit_by_pitch') or 0
        sacrifices = totals.get('sacrifices') or 0
        singles = totals.get('singles') or 0
        doubles = totals.get('doubles') or 0
        triples = totals.get('triples') or 0
        home_runs = totals.get('home_runs') or 0
        plate_appearances = at_bats + walks + hit_by_pitch + sacrifices
        batting_average = round(hits / at_bats, 3) if at_bats else 0.0
        raw_on_base_percentage = ((hits + walks + hit_by_pitch) / plate_appearances) if plate_appearances else 0.0
        on_base_percentage = round(raw_on_base_percentage, 3)
        total_bases = singles + (2 * doubles) + (3 * triples) + (4 * home_runs)
        raw_slugging_percentage = (total_bases / at_bats) if at_bats else 0.0
        slugging_percentage = round(raw_slugging_percentage, 3)

        results.append({
            'player': entry.player,
            'team': entry.team,
            'at_bats': at_bats,
            'runs': totals.get('runs') or 0,
            'hits': hits,
            'doubles': doubles,
            'triples': triples,
            'home_runs': home_runs,
            'rbis': totals.get('rbis') or 0,
            'walks': walks,
            'strikeouts': totals.get('strikeouts') or 0,
            'batting_average': batting_average,
            'on_base_percentage': on_base_percentage,
            'slugging_percentage': slugging_percentage,
            'on_base_plus_slugging': round(raw_on_base_percentage + raw_slugging_percentage, 3),
        })

    return results


def batting_leaderboard(competition, min_at_bats=10):
    """Returns players sorted by competition batting average, descending."""
    lines = (
        BattingStatLine.objects
        .filter(game__competition=competition)
        .values('player__id', 'player__first_name', 'player__last_name')
        .annotate(
            total_at_bats=Sum('at_bats'),
            total_hits=Sum('hits'),
        )
        .filter(total_at_bats__gte=min_at_bats)
    )

    results = []
    for line in lines:
        avg = round(line['total_hits'] / line['total_at_bats'], 3) if line['total_at_bats'] else 0.0
        results.append({**line, 'batting_average': avg})

    return sorted(results, key=lambda r: r['batting_average'], reverse=True)


def rbi_leaderboard(competition):
    """Returns players sorted by total competition RBIs, descending."""
    lines = (
        BattingStatLine.objects
        .filter(game__competition=competition)
        .values('player__id', 'player__first_name', 'player__last_name')
        .annotate(total_rbis=Sum('rbis'))
    )

    return sorted(lines, key=lambda r: r['total_rbis'], reverse=True)


def runs_leaderboard(competition):
    """Returns players sorted by total competition runs scored, descending."""
    lines = (
        BattingStatLine.objects
        .filter(game__competition=competition)
        .values('player__id', 'player__first_name', 'player__last_name')
        .annotate(total_runs=Sum('runs'))
    )

    return sorted(lines, key=lambda r: r['total_runs'], reverse=True)


def era_leaderboard(competition, min_innings=5):
    """Returns pitchers sorted by competition ERA, ascending (lower is better)."""
    lines = (
        PitchingStatLine.objects
        .filter(game__competition=competition)
        .values('player__id', 'player__first_name', 'player__last_name')
        .annotate(
            total_innings=Sum('innings_pitched'),
            total_earned_runs=Sum('earned_runs'),
        )
        .filter(total_innings__gte=min_innings)
    )

    results = []
    for line in lines:
        era = round((line['total_earned_runs'] * 9) / float(line['total_innings']), 2) if line['total_innings'] else 0.0
        results.append({**line, 'era': era})

    return sorted(results, key=lambda r: r['era'])
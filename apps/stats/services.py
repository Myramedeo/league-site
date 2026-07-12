from django.db.models import Sum, F, Q
from .models import BattingStatLine, PitchingStatLine

def batting_leaderboard(season, min_at_bats=10):
    """Returns players sorted by season batting average, descending."""
    lines = (
        BattingStatLine.objects
        .filter(game__season=season)
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


def era_leaderboard(season, min_innings=5):
    """Returns pitchers sorted by season ERA, ascending (lower is better)."""
    lines = (
        PitchingStatLine.objects
        .filter(game__season=season)
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
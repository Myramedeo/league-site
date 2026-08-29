from teams.models import Season


def get_selected_season(request):
    """Resolve the season to display from the `?season=<year>` query param,
    falling back to the most recent season if absent or invalid."""
    year = request.GET.get('season')
    season = None
    if year:
        season = Season.objects.filter(year=year).first()
    if season is None:
        season = Season.objects.order_by('-year').first()
    return season

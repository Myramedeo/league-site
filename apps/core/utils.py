from teams.models import Competition


def get_selected_competition(request):
    """Resolve the competition to display from the `?competition=<id>` query param,
    falling back to the most recently created competition if absent or invalid."""
    competition_id = request.GET.get('competition')
    competition = None
    if competition_id:
        competition = Competition.objects.select_related('season').filter(id=competition_id).first()
    if competition is None:
        competition = Competition.objects.select_related('season').order_by('-id').first()
    return competition

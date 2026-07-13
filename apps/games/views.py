from rest_framework import viewsets
from .models import Game
from .serializers import GameSerializer

class GameViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Game.objects.select_related('home_team', 'away_team', 'result').order_by('date')
    serializer_class = GameSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        season_id = self.request.query_params.get('season')
        if season_id:
            qs = qs.filter(season_id=season_id)
        return qs
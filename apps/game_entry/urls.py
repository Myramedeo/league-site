from django.urls import path

from .views import (
    game_workspace,
    portal,
    record_plate_appearance_fragment,
    save_lineups_fragment,
    staff_sign_in,
    substitution_fragment,
    update_game_state_fragment,
)

app_name = 'game_entry'

urlpatterns = [
    path('sign-in/', staff_sign_in, name='sign_in'),
    path('', portal, name='portal'),
    path('games/<int:game_id>/', game_workspace, name='game_workspace'),
    path('games/<int:game_id>/state/', update_game_state_fragment, name='game_state_fragment'),
    path('games/<int:game_id>/plate-appearance/', record_plate_appearance_fragment, name='plate_appearance_fragment'),
    path('games/<int:game_id>/lineups/', save_lineups_fragment, name='lineups_fragment'),
    path('games/<int:game_id>/substitution/<str:team_key>/', substitution_fragment, name='substitution_fragment'),
]
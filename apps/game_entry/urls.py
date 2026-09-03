from django.urls import path

from .views import (
    add_inning,
    add_play,
    delete_play,
    edit_play,
    finalize_game,
    game_workspace,
    lineup_slot,
    portal,
    staff_sign_in,
    unfinalize_game,
)

app_name = 'game_entry'

urlpatterns = [
    path('sign-in/', staff_sign_in, name='sign_in'),
    path('', portal, name='portal'),
    path('games/<int:game_id>/', game_workspace, name='game_workspace'),
    path('games/<int:game_id>/lineup/<str:team_key>/<int:order>/', lineup_slot, name='lineup_slot'),
    path('games/<int:game_id>/plays/<str:team_key>/', add_play, name='add_play'),
    path('games/<int:game_id>/plays/<int:entry_id>/edit/', edit_play, name='edit_play'),
    path('games/<int:game_id>/plays/<int:entry_id>/delete/', delete_play, name='delete_play'),
    path('games/<int:game_id>/innings/add/', add_inning, name='add_inning'),
    path('games/<int:game_id>/finalize/', finalize_game, name='finalize'),
    path('games/<int:game_id>/unfinalize/', unfinalize_game, name='unfinalize'),
]
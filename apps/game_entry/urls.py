from django.urls import path

from .views import game_workspace, portal, staff_sign_in

app_name = 'game_entry'

urlpatterns = [
    path('sign-in/', staff_sign_in, name='sign_in'),
    path('', portal, name='portal'),
    path('games/<int:game_id>/', game_workspace, name='game_workspace'),
]
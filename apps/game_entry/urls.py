from django.urls import path

from .views import game_workspace, portal

app_name = 'game_entry'

urlpatterns = [
    path('', portal, name='portal'),
    path('games/<int:game_id>/', game_workspace, name='game_workspace'),
]
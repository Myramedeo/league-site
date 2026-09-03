"""
URL configuration for league_site project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from core import views as core_views

from rest_framework.routers import DefaultRouter
from teams.views import TeamViewSet, SeasonViewSet
from players.views import PlayerViewSet
from games.views import GameViewSet, game_detail
from core.views import standings_api
from announcements.views import AnnouncementViewSet

from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

router = DefaultRouter()
router.register('announcements', AnnouncementViewSet, basename='announcement')
router.register('teams', TeamViewSet)
router.register('seasons', SeasonViewSet)
router.register('players', PlayerViewSet)
router.register('games', GameViewSet)

urlpatterns = [
    path('_nested_admin/', include('nested_admin.urls')),
    path('ckeditor5/', include('django_ckeditor_5.urls')),
    path('admin/', admin.site.urls),
    path('game-entry/', include('game_entry.urls')),
    path('newsletter/', include('newsletter.urls')),
    path('teams/', include('teams.urls')),
    path('players/', include('players.urls')),
    path('photos/', include('photos.urls')),
    path('games/<int:game_id>/', game_detail, name='game_detail'),
    path('standings/', core_views.standings, name='standings'),
    path('stats/', core_views.leaderboards, name='leaderboards'),
    path('schedule/', core_views.schedule, name='schedule'),
    path('articles/', core_views.article_list, name='article_list'),
    path('articles/<slug:slug>/', core_views.article_detail, name='article_detail'),
    path('', core_views.home, name='home'),
    path('api/', include(router.urls)),
    path('api/standings/', standings_api, name='standings_api'),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='docs'),
]

if settings.DEBUG:
    # Include django_browser_reload URLs only in DEBUG mode
    urlpatterns += [
        path("__reload__/", include("django_browser_reload.urls")),
    ]
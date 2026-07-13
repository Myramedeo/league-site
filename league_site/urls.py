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
from core import views as core_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('teams/', include('teams.urls')),
    path('players/', include('players.urls')),
    path('standings/', core_views.standings, name='standings'),
    path('stats/', core_views.leaderboards, name='leaderboards'),
    path('schedule/', core_views.schedule, name='schedule'),
    path('', core_views.standings, name='home'),  # simplest homepage: redirect to standings
]

from django.contrib import admin
from .models import Game, GameResult
from stats.admin import BattingStatLineInline, PitchingStatLineInline

class GameResultInline(admin.StackedInline):
    model = GameResult
    extra = 0  # 0 because it's one-to-one, don't offer a blank second result

@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ('date', 'scheduled_time', 'status', 'venue', 'away_team', 'home_team', 'season')
    list_filter = ('season', 'home_team', 'away_team', 'status')
    date_hierarchy = 'date'
    inlines = [GameResultInline, BattingStatLineInline, PitchingStatLineInline]
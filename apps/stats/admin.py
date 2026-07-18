import nested_admin
from django.contrib import admin
from .models import BattingStatLine, PitchingStatLine

@admin.register(BattingStatLine)
class BattingStatLineAdmin(admin.ModelAdmin):
    list_display = ('player', 'game', 'at_bats', 'hits', 'batting_average')
    list_filter = ('game__season',)
    search_fields = ('player__first_name', 'player__last_name')

@admin.register(PitchingStatLine)
class PitchingStatLineAdmin(admin.ModelAdmin):
    list_display = ('player', 'game', 'innings_pitched', 'earned_runs', 'era')
    list_filter = ('game__season',)
    search_fields = ('player__first_name', 'player__last_name')

class BattingStatLineInline(nested_admin.NestedTabularInline):
    model = BattingStatLine
    extra = 1
    autocomplete_fields = ['player']

class PitchingStatLineInline(nested_admin.NestedTabularInline):
    model = PitchingStatLine
    extra = 1
    autocomplete_fields = ['player']
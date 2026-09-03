from django.contrib import admin

from .models import BattingSlot, GameScorecard, ScorecardEntry


class BattingSlotInline(admin.TabularInline):
	model = BattingSlot
	extra = 0


@admin.register(GameScorecard)
class GameScorecardAdmin(admin.ModelAdmin):
	list_display = ('game', 'created_by', 'is_finalized', 'displayed_innings', 'created_at')
	list_filter = ('is_finalized', 'game__season')
	search_fields = ('game__home_team__name', 'game__away_team__name')
	inlines = [BattingSlotInline]


@admin.register(ScorecardEntry)
class ScorecardEntryAdmin(admin.ModelAdmin):
	list_display = ('scorecard', 'team', 'inning', 'half_inning', 'play_index', 'batter', 'result', 'rbi', 'created_at')
	list_filter = ('result', 'team', 'scorecard__game__season')
	search_fields = ('slot__player__first_name', 'slot__player__last_name', 'notes', 'notation')


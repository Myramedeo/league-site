from django.contrib import admin

from .models import LineupSpot, LineupSubstitution, PlateAppearance, ScoringSession, TeamLineup


class LineupSpotInline(admin.TabularInline):
	model = LineupSpot
	extra = 0


@admin.register(TeamLineup)
class TeamLineupAdmin(admin.ModelAdmin):
	list_display = ('team', 'session', 'batting_index')
	list_filter = ('team', 'session__game__season')
	inlines = [LineupSpotInline]


@admin.register(ScoringSession)
class ScoringSessionAdmin(admin.ModelAdmin):
	list_display = ('game', 'started_by', 'lineups_locked', 'current_inning', 'half_inning', 'outs', 'created_at')
	list_filter = ('lineups_locked', 'game__season')
	search_fields = ('game__home_team__name', 'game__away_team__name')


@admin.register(PlateAppearance)
class PlateAppearanceAdmin(admin.ModelAdmin):
	list_display = ('session', 'inning_number', 'half_inning', 'outs_before', 'offense_team', 'batter', 'result', 'created_at')
	list_filter = ('result', 'offense_team', 'session__game__season')
	search_fields = ('batter__first_name', 'batter__last_name', 'notes')


@admin.register(LineupSubstitution)
class LineupSubstitutionAdmin(admin.ModelAdmin):
	list_display = ('session', 'team', 'batting_order', 'outgoing_player', 'incoming_player', 'created_at')
	list_filter = ('team', 'session__game__season')
	search_fields = (
		'outgoing_player__first_name',
		'outgoing_player__last_name',
		'incoming_player__first_name',
		'incoming_player__last_name',
	)

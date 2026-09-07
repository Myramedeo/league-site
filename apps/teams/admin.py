from django.contrib import admin
from .models import Competition, Season, Team


class CompetitionInline(admin.TabularInline):
    model = Competition
    extra = 0
    fields = ('name', 'phase', 'source_order', 'expected_team_count')


@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    list_display = ('year', 'name')
    ordering = ('-year',)
    inlines = (CompetitionInline,)


@admin.register(Competition)
class CompetitionAdmin(admin.ModelAdmin):
    list_display = ('name', 'season', 'phase', 'source_order')
    list_filter = ('season', 'phase')
    search_fields = ('name',)
    ordering = ('-season__year', 'source_order', 'name')

@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)
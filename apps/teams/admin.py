from django.contrib import admin
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse

from players.models import Roster

from .models import Competition, Season, Team


class CompetitionInline(admin.TabularInline):
    model = Competition
    extra = 0
    fields = ('name', 'phase', 'source_order', 'expected_team_count')


@admin.action(description='Copy Regular Season rosters to Playoffs')
def copy_regular_rosters_to_playoffs(modeladmin, request, queryset):
    if queryset.count() != 1:
        modeladmin.message_user(
            request,
            'Select exactly one Playoffs competition.',
            level=messages.ERROR,
        )
        return

    target = queryset.first()
    if target.phase != 'PLAYOFFS':
        modeladmin.message_user(
            request,
            'The selected competition must be a Playoffs competition.',
            level=messages.ERROR,
        )
        return

    regular_competitions = Competition.objects.filter(
        season=target.season,
        phase='REGULAR',
    ).order_by('source_order', 'name')
    if not regular_competitions.exists():
        modeladmin.message_user(
            request,
            'No Regular Season competition exists for the selected season.',
            level=messages.ERROR,
        )
        return

    if 'confirm_copy' not in request.POST:
        return TemplateResponse(
            request,
            'admin/teams/copy_rosters.html',
            {
                **modeladmin.admin_site.each_context(request),
                'opts': modeladmin.model._meta,
                'target': target,
                'regular_competitions': regular_competitions,
                'selected_action': target.pk,
                'cancel_url': reverse('admin:teams_competition_changelist'),
            },
        )

    try:
        source = regular_competitions.get(pk=request.POST.get('source_competition_id'))
    except (Competition.DoesNotExist, Competition.MultipleObjectsReturned):
        modeladmin.message_user(
            request,
            'Choose a valid Regular Season competition from the selected season.',
            level=messages.ERROR,
        )
        return HttpResponseRedirect(reverse('admin:teams_competition_changelist'))

    source_rosters = list(
        Roster.objects.filter(competition=source).values(
            'player_id', 'team_id', 'season_id', 'show_in_team_list'
        )
    )
    existing_keys = set(
        Roster.objects.filter(competition=target).values_list(
            'player_id', 'team_id', 'season_id'
        )
    )
    rosters_to_create = [
        Roster(
            player_id=roster['player_id'],
            team_id=roster['team_id'],
            season_id=roster['season_id'],
            competition=target,
            show_in_team_list=roster['show_in_team_list'],
        )
        for roster in source_rosters
        if (
            roster['player_id'],
            roster['team_id'],
            roster['season_id'],
        ) not in existing_keys
    ]

    with transaction.atomic():
        Roster.objects.bulk_create(rosters_to_create, ignore_conflicts=True)

    modeladmin.message_user(
        request,
        f'Copied {len(rosters_to_create)} roster record(s) from {source} to {target}; '
        f'{len(source_rosters) - len(rosters_to_create)} already existed.',
        level=messages.SUCCESS,
    )
    return HttpResponseRedirect(reverse('admin:teams_competition_changelist'))


@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    list_display = ('year', 'name')
    ordering = ('-year',)
    inlines = (CompetitionInline,)


@admin.register(Competition)
class CompetitionAdmin(admin.ModelAdmin):
    exclude = ("expected_team_count", "legacy_division_id")

    list_display = ('name', 'season', 'phase', 'source_order')
    list_filter = ('season', 'phase')
    search_fields = ('name',)
    ordering = ('-season__year', 'source_order', 'name')
    actions = [copy_regular_rosters_to_playoffs]

@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)
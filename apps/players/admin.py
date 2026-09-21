from django.contrib import admin
from django.contrib.admin import helpers
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse

from .models import Player, PlayerMergeAudit, Roster
from .services import find_duplicate_players, merge_players, undo_player_merge


class RosterInline(admin.TabularInline):
    model = Roster
    extra = 1


@admin.action(description='Find likely duplicate names among the selected players')
def find_duplicate_selected_players(modeladmin, request, queryset):
    players = list(queryset.order_by('last_name', 'first_name')) if queryset.exists() else list(Player.objects.order_by('last_name', 'first_name'))
    matches = find_duplicate_players(players=players, threshold=0.8)

    if not matches:
        modeladmin.message_user(request, 'No likely duplicate names were found.', level=messages.INFO)
        return

    preview = '; '.join(
        f'{match["left"]} / {match["right"]} ({match["score"]:.2f})'
        for match in matches[:10]
    )
    if len(matches) > 10:
        preview = f'{preview} ... and {len(matches) - 10} more.'

    modeladmin.message_user(request, f'Likely duplicates: {preview}', level=messages.WARNING)


@admin.action(description='Merge selected players into the first selected record')
def merge_selected_players(modeladmin, request, queryset):
    selected = list(queryset.order_by('last_name', 'first_name'))
    if len(selected) < 2:
        modeladmin.message_user(request, 'Select at least two players to merge.', level=messages.ERROR)
        return

    target = selected[0]
    if 'confirm_merge' not in request.POST:
        return TemplateResponse(
            request,
            'admin/players/confirm_merge.html',
            {
                **modeladmin.admin_site.each_context(request),
                'opts': modeladmin.model._meta,
                'players': selected,
                'target': target,
                'action_checkbox_name': helpers.ACTION_CHECKBOX_NAME,
                'cancel_url': reverse('admin:players_player_changelist'),
            },
        )

    audit_ids = []
    for source in selected[1:]:
        source_id = source.pk
        merge_players(target, source, merged_by=request.user)
        audit_ids.append(str(PlayerMergeAudit.objects.get(
            target_player_id=target.pk,
            source_player_id=source_id,
        ).pk))

    modeladmin.message_user(
        request,
        f'Merged {len(selected) - 1} duplicate player(s) into {target}. Audit ID(s): {", ".join(audit_ids)}.',
        level=messages.SUCCESS,
    )
    return HttpResponseRedirect(request.get_full_path())


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ('last_name', 'first_name', 'jersey_number')
    search_fields = ('first_name', 'last_name')
    inlines = [RosterInline]
    actions = [find_duplicate_selected_players, merge_selected_players]


@admin.register(Roster)
class RosterAdmin(admin.ModelAdmin):
    list_display = ('player', 'team', 'season', 'show_in_team_list')
    list_filter = ('season', 'team')


@admin.action(description='Undo selected player merge')
def undo_selected_player_merges(modeladmin, request, queryset):
    for audit in queryset:
        try:
            undo_player_merge(audit)
        except ValueError as error:
            modeladmin.message_user(request, f'{audit}: {error}', level=messages.ERROR)
            continue
        modeladmin.message_user(request, f'Undid merge: {audit}.', level=messages.SUCCESS)


@admin.register(PlayerMergeAudit)
class PlayerMergeAuditAdmin(admin.ModelAdmin):
    list_display = ('source_name', 'target_name', 'merged_at', 'merged_by', 'undone_at')
    list_filter = ('undone_at', 'merged_at')
    search_fields = ('source_name', 'target_name')
    readonly_fields = (
        'target_player', 'source_player_id', 'target_name', 'source_name',
        'before_state', 'after_state', 'merged_at', 'undone_at', 'merged_by',
    )
    actions = [undo_selected_player_merges]
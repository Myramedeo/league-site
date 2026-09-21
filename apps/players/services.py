import json
from difflib import SequenceMatcher

from django.db import transaction
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone

from game_entry.models import BattingSlot, ScorecardEntry
from players.models import LegacyPlayerIdentity, Player, PlayerMergeAudit, Roster
from stats.models import BattingStatLine, PitchingStatLine

BATTLING_FIELDS = [
    'at_bats', 'runs', 'hits', 'rbis', 'walks', 'strikeouts',
    'singles', 'doubles', 'triples', 'home_runs', 'hit_by_pitch',
    'stolen_bases', 'sacrifices', 'reached_on_error',
]
PITCHING_FIELDS = [
    'innings_pitched', 'hits_allowed', 'runs_allowed', 'earned_runs',
    'walks_allowed', 'strikeouts', 'pitches_thrown',
]


def normalize_player_name(value):
    if not value:
        return ''
    cleaned = value.lower().replace('.', '').replace("'", '').replace('-', '').replace(' ', '')
    return ''.join(ch for ch in cleaned if ch.isalnum())


def score_player_name_similarity(first_name_a, last_name_a, first_name_b, last_name_b):
    left_first = normalize_player_name(first_name_a)
    right_first = normalize_player_name(first_name_b)
    left_last = normalize_player_name(last_name_a)
    right_last = normalize_player_name(last_name_b)

    if left_last and right_last:
        last_similarity = SequenceMatcher(None, left_last, right_last).ratio()
    else:
        last_similarity = 0.0

    first_similarity = SequenceMatcher(None, left_first, right_first).ratio()
    first_initial_match = bool(left_first and right_first and left_first[0] == right_first[0])

    if left_last and right_last and left_last == right_last:
        if left_first == right_first or first_initial_match:
            return 1.0
        return max(first_similarity, 0.75)

    if left_last and right_last and last_similarity >= 0.8 and (first_similarity >= 0.75 or first_initial_match):
        return round((last_similarity + max(first_similarity, 0.7)) / 2, 3)

    if left_first and right_first and (left_first == right_first or first_similarity >= 0.85):
        return round(max(first_similarity, 0.85), 3)

    return round(max(first_similarity, last_similarity), 3)


def find_duplicate_players(players=None, threshold=0.8):
    """Return likely duplicate player pairs with a match score between 0 and 1."""
    queryset = players if players is not None else Player.objects.order_by('last_name', 'first_name')
    player_list = list(queryset)
    matches = []

    for index, left in enumerate(player_list):
        for right in player_list[index + 1:]:
            score = score_player_name_similarity(
                left.first_name,
                left.last_name,
                right.first_name,
                right.last_name,
            )
            if score >= threshold:
                matches.append({
                    'left': left,
                    'right': right,
                    'score': score,
                })

    return matches


AUDIT_MODELS = (
    Player,
    BattingStatLine,
    PitchingStatLine,
    Roster,
    BattingSlot,
    ScorecardEntry,
    LegacyPlayerIdentity,
)


def _field_values(instance):
    return {
        field.attname: getattr(instance, field.attname)
        for field in instance._meta.concrete_fields
    }


def _snapshot_player_data(player_ids):
    player_ids = set(player_ids)
    rows = []
    for model in AUDIT_MODELS:
        if model is Player:
            queryset = model.objects.filter(id__in=player_ids)
        elif model is ScorecardEntry:
            slot_ids = BattingSlot.objects.filter(player_id__in=player_ids).values('id')
            queryset = model.objects.filter(slot_id__in=slot_ids)
        else:
            queryset = model.objects.filter(player_id__in=player_ids)

        for instance in queryset.order_by('pk'):
            rows.append({
                'model': model._meta.label,
                'pk': instance.pk,
                'values': _field_values(instance),
            })

    encoded = DjangoJSONEncoder().encode(sorted(rows, key=lambda row: (row['model'], row['pk'])))
    return encoded


def _restore_snapshot(snapshot):
    rows = json.loads(snapshot)

    for model in (Player, Roster, BattingStatLine, PitchingStatLine, BattingSlot, ScorecardEntry, LegacyPlayerIdentity):
        for row in rows:
            if row['model'] != model._meta.label:
                continue
            model.objects.update_or_create(pk=row['pk'], defaults=row['values'])


@transaction.atomic
def undo_player_merge(audit):
    """Restore a merge only if its affected records are unchanged since merging."""
    audit = PlayerMergeAudit.objects.select_for_update().get(pk=audit.pk)
    if audit.is_undone:
        raise ValueError('This player merge has already been undone.')

    target_player_id = audit.target_player_id
    current_state = _snapshot_player_data([target_player_id, audit.source_player_id])
    if current_state != audit.after_state:
        raise ValueError('The merged player data has changed since this merge; undo was not performed.')

    current_rows = json.loads(current_state)
    for model in (ScorecardEntry, BattingSlot, BattingStatLine, PitchingStatLine, Roster, LegacyPlayerIdentity, Player):
        model.objects.filter(pk__in=[
            row['pk'] for row in current_rows if row['model'] == model._meta.label
        ]).delete()

    _restore_snapshot(audit.before_state)
    audit.undone_at = timezone.now()
    audit.target_player_id = target_player_id
    audit.save(update_fields=['undone_at', 'target_player'])
    return audit


@transaction.atomic
def merge_players(target_player, source_player, keep_jersey=True, merged_by=None):
    """
    Merge source_player into target_player while preserving all related game data.
    The source player is deleted at the end of the transaction.
    """
    if target_player.id == source_player.id:
        return target_player

    before_state = _snapshot_player_data([target_player.id, source_player.id])
    target_name = str(target_player)
    source_name = str(source_player)
    source_player_id = source_player.id

    if keep_jersey and not target_player.jersey_number and source_player.jersey_number:
        target_player.jersey_number = source_player.jersey_number
        target_player.save(update_fields=['jersey_number'])

    for source_line in BattingStatLine.objects.filter(player=source_player):
        target_line = BattingStatLine.objects.filter(player=target_player, game=source_line.game).first()
        if target_line is None:
            source_line.player = target_player
            source_line.save(update_fields=['player'])
            continue

        for field in BATTLING_FIELDS:
            setattr(target_line, field, getattr(target_line, field) + getattr(source_line, field))
        target_line.save()
        source_line.delete()

    for source_line in PitchingStatLine.objects.filter(player=source_player):
        target_line = PitchingStatLine.objects.filter(player=target_player, game=source_line.game).first()
        if target_line is None:
            source_line.player = target_player
            source_line.save(update_fields=['player'])
            continue

        for field in PITCHING_FIELDS:
            setattr(target_line, field, getattr(target_line, field) + getattr(source_line, field))
        target_line.save()
        source_line.delete()

    for source_roster in Roster.objects.filter(player=source_player):
        target_roster = Roster.objects.filter(
            player=target_player,
            team=source_roster.team,
            season=source_roster.season,
            competition=source_roster.competition,
        ).first()

        if target_roster is None:
            source_roster.player = target_player
            source_roster.save(update_fields=['player'])
            continue

        target_roster.show_in_team_list = target_roster.show_in_team_list or source_roster.show_in_team_list
        target_roster.save(update_fields=['show_in_team_list'])
        source_roster.delete()

    for source_slot in BattingSlot.objects.filter(player=source_player):
        target_slot = BattingSlot.objects.filter(
            scorecard=source_slot.scorecard,
            team=source_slot.team,
            player=target_player,
        ).first()

        if target_slot is None:
            source_slot.player = target_player
            source_slot.save(update_fields=['player'])
            continue

        ScorecardEntry.objects.filter(slot=source_slot).update(slot=target_slot)
        source_slot.delete()

    LegacyPlayerIdentity.objects.filter(player=source_player).update(player=target_player)

    source_player.delete()
    PlayerMergeAudit.objects.create(
        target_player_id=target_player.id,
        source_player_id=source_player_id,
        target_name=target_name,
        source_name=source_name,
        before_state=before_state,
        after_state=_snapshot_player_data([target_player.id, source_player.id]),
        merged_by=merged_by,
    )
    return target_player

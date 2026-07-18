import nested_admin
from django.contrib import admin
from .models import Game, GameResult, InningScore
from stats.admin import BattingStatLineInline, PitchingStatLineInline

from django.forms.models import BaseInlineFormSet
from django.core.exceptions import ValidationError

class InningScoreFormSet(BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for i, form in enumerate(self.forms, start=1):
            if not form.instance.pk:
                form.initial["inning"] = i

    def clean(self):
        super().clean()

        innings = [
            form.cleaned_data.get("inning")
            for form in self.forms
            if form.cleaned_data and not form.cleaned_data.get("DELETE")
        ]

        if len(innings) > 9:
            raise ValidationError(
                "Runs can only be recorded for up to 9 innings."
            )

class InningScoreInline(nested_admin.NestedTabularInline):
    model = InningScore
    formset = InningScoreFormSet
    fields = ("inning", "away_runs", "home_runs")

    def get_extra(self, request, obj=None, **kwargs):
        if obj is None:
            return 9

        if hasattr(obj, "innings"):
            existing = obj.innings.count()
        elif hasattr(obj, "result"):
            existing = obj.result.innings.count()
        else:
            existing = 0

        return max(0, 9 - existing)

class GameResultInline(nested_admin.NestedStackedInline):
    model = GameResult
    extra = 0
    inlines = [InningScoreInline]

@admin.register(Game)
class GameAdmin(nested_admin.NestedModelAdmin):
    list_display = (
        'date',
        'scheduled_time',
        'status',
        'venue',
        'away_team',
        'home_team',
        'season'
    )
    inlines = [
        GameResultInline,
        BattingStatLineInline,
        PitchingStatLineInline
    ]

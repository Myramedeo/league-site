from django import forms

from game_entry.models import ScorecardEntry

SELECT_STYLE = 'w-full rounded-md border border-[#3F5847] bg-[#132119] px-3 py-2 text-sm text-[#F2F0E6] focus:border-[#E8B23D] focus:outline-none'


class BattingSlotForm(forms.Form):
    player = forms.ModelChoiceField(queryset=None, empty_label='Select player')

    def __init__(self, *args, roster_queryset, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['player'].queryset = roster_queryset
        self.fields['player'].widget.attrs.update({'class': SELECT_STYLE})


class ScorecardEntryForm(forms.Form):
    result = forms.ChoiceField(choices=ScorecardEntry.RESULT_CHOICES)
    outs_recorded = forms.IntegerField(min_value=0, max_value=3)
    rbi = forms.IntegerField(min_value=0, max_value=4)
    batter_ending_base = forms.ChoiceField(choices=ScorecardEntry.BASE_OUTCOME_CHOICES)
    runner_1st_ending = forms.ChoiceField(
        choices=[('', 'No runner')] + ScorecardEntry.BASE_OUTCOME_CHOICES, required=False,
    )
    runner_2nd_ending = forms.ChoiceField(
        choices=[('', 'No runner')] + ScorecardEntry.BASE_OUTCOME_CHOICES, required=False,
    )
    runner_3rd_ending = forms.ChoiceField(
        choices=[('', 'No runner')] + ScorecardEntry.BASE_OUTCOME_CHOICES, required=False,
    )
    notation = forms.CharField(max_length=20, required=False)
    notes = forms.CharField(max_length=255, required=False)

    def __init__(self, *args, runners_before, **kwargs):
        super().__init__(*args, **kwargs)
        runner_1st, runner_2nd, runner_3rd = runners_before
        for field_name in self.fields:
            self.fields[field_name].widget.attrs.update({'class': SELECT_STYLE})
        # Only show a runner's ending-base field when that base was actually occupied.
        if not runner_1st:
            del self.fields['runner_1st_ending']
        if not runner_2nd:
            del self.fields['runner_2nd_ending']
        if not runner_3rd:
            del self.fields['runner_3rd_ending']


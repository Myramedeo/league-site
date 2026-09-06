from django import forms

from game_entry.models import ScorecardEntry

SELECT_STYLE = 'w-full rounded-md border border-[#3F5847] bg-[#132119] px-3 py-2 text-sm text-[#F2F0E6] focus:border-[#E8B23D] focus:outline-none'


class BattingSlotForm(forms.Form):
    player = forms.ModelChoiceField(queryset=None, empty_label='-----------')

    def __init__(self, *args, roster_queryset, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['player'].queryset = roster_queryset
        # autocomplete="off" discourages browsers from restoring stale selected
        # values over the server-rendered ones when the page is reloaded.
        self.fields['player'].widget.attrs.update({'class': SELECT_STYLE, 'autocomplete': 'off'})


class ScorecardEntryForm(forms.Form):
    result = forms.ChoiceField(choices=ScorecardEntry.RESULT_CHOICES)
    outs_recorded = forms.IntegerField(min_value=0, max_value=3)
    rbi = forms.IntegerField(min_value=0, max_value=4)
    scored = forms.BooleanField(required=False)
    notation = forms.CharField(max_length=20, required=False)
    notes = forms.CharField(max_length=255, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name != 'scored':
                field.widget.attrs.update({'class': SELECT_STYLE})



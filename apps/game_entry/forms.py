from django import forms

from game_entry.models import ScoringSession


class TeamLineupForm(forms.Form):
    MAX_LINEUP_SIZE = 12

    lineup_size = forms.IntegerField(min_value=1, max_value=MAX_LINEUP_SIZE)

    def __init__(self, *args, roster_queryset, team_label, initial_players=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.roster_count = roster_queryset.count()
        self.fields['lineup_size'].label = f"{team_label} lineup size"
        self.fields['lineup_size'].widget.attrs.update({
            'class': 'w-full rounded-md border border-[#3F5847] bg-[#132119] px-3 py-2 text-sm text-[#F2F0E6] focus:border-[#E8B23D] focus:outline-none',
        })

        default_size = min(9, self.roster_count) if self.roster_count else 1

        if initial_players:
            default_size = len(initial_players)
        self.fields['lineup_size'].initial = default_size

        self.fields['lineup_size'].help_text = f"Available roster players: {self.roster_count}"

        for order in range(1, self.MAX_LINEUP_SIZE + 1):
            field_name = f'spot_{order}'
            self.fields[field_name] = forms.ModelChoiceField(
                queryset=roster_queryset,
                required=False,
                label=f"Spot {order}",
                empty_label='Select player',
            )
            self.fields[field_name].widget.attrs.update({
                'class': 'w-full rounded-md border border-[#3F5847] bg-[#132119] px-3 py-2 text-sm text-[#F2F0E6] focus:border-[#E8B23D] focus:outline-none',
            })
            if initial_players and order <= len(initial_players):
                self.initial[field_name] = initial_players[order - 1]

    def clean(self):
        cleaned_data = super().clean()
        lineup_size = cleaned_data.get('lineup_size')
        if not lineup_size:
            return cleaned_data
        if lineup_size > self.roster_count:
            self.add_error('lineup_size', 'Lineup size cannot exceed available roster players.')
            return cleaned_data

        selected_players = []
        seen_player_ids = set()

        for order in range(1, lineup_size + 1):
            player = cleaned_data.get(f'spot_{order}')
            if not player:
                self.add_error(f'spot_{order}', 'Select a player for this batting order spot.')
                continue
            if player.id in seen_player_ids:
                self.add_error(f'spot_{order}', 'This player is already in the lineup.')
                continue
            seen_player_ids.add(player.id)
            selected_players.append(player)

        cleaned_data['ordered_players'] = selected_players
        return cleaned_data


class GameStateForm(forms.Form):
    current_inning = forms.IntegerField(min_value=1)
    half_inning = forms.ChoiceField(choices=ScoringSession.HALF_INNING_CHOICES)
    outs = forms.IntegerField(min_value=0, max_value=2)
    first_base_runner = forms.ModelChoiceField(queryset=None, required=False, empty_label='Empty')
    second_base_runner = forms.ModelChoiceField(queryset=None, required=False, empty_label='Empty')
    third_base_runner = forms.ModelChoiceField(queryset=None, required=False, empty_label='Empty')

    def __init__(self, *args, player_queryset, **kwargs):
        super().__init__(*args, **kwargs)
        select_style = 'w-full rounded-md border border-[#3F5847] bg-[#132119] px-3 py-2 text-sm text-[#F2F0E6] focus:border-[#E8B23D] focus:outline-none'
        for field_name in ('first_base_runner', 'second_base_runner', 'third_base_runner'):
            self.fields[field_name].queryset = player_queryset
            self.fields[field_name].widget.attrs.update({'class': select_style})
        for field_name in ('current_inning', 'outs'):
            self.fields[field_name].widget.attrs.update({'class': select_style})
        self.fields['half_inning'].widget.attrs.update({'class': select_style})


class LineupSubstitutionForm(forms.Form):
    batting_order = forms.IntegerField(min_value=1)
    incoming_player = forms.ModelChoiceField(queryset=None)
    notes = forms.CharField(max_length=255, required=False)

    def __init__(self, *args, lineup, roster_queryset, **kwargs):
        super().__init__(*args, **kwargs)
        self.lineup = lineup
        self.fields['incoming_player'].queryset = roster_queryset
        style = 'w-full rounded-md border border-[#3F5847] bg-[#132119] px-3 py-2 text-sm text-[#F2F0E6] focus:border-[#E8B23D] focus:outline-none'
        self.fields['batting_order'].widget.attrs.update({'class': style})
        self.fields['incoming_player'].widget.attrs.update({'class': style})
        self.fields['notes'].widget.attrs.update({'class': style, 'placeholder': 'Optional substitution note'})

    def clean(self):
        cleaned_data = super().clean()
        batting_order = cleaned_data.get('batting_order')
        incoming_player = cleaned_data.get('incoming_player')
        if not batting_order or not incoming_player:
            return cleaned_data

        try:
            spot = self.lineup.spots.select_related('player').get(batting_order=batting_order)
        except self.lineup.spots.model.DoesNotExist:
            self.add_error('batting_order', 'That batting order slot does not exist in this lineup.')
            return cleaned_data

        if self.lineup.spots.filter(player=incoming_player).exists() and incoming_player != spot.player:
            self.add_error('incoming_player', 'That player is already in this lineup.')
            return cleaned_data

        if incoming_player == spot.player:
            self.add_error('incoming_player', 'Choose a different player for substitution.')
            return cleaned_data

        cleaned_data['spot'] = spot
        cleaned_data['outgoing_player'] = spot.player
        return cleaned_data

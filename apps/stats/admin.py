import nested_admin
from django.contrib import admin
from .models import BattingStatLine

@admin.register(BattingStatLine)
class BattingStatLineAdmin(admin.ModelAdmin):
    list_display = ('player', 'game', 'at_bats', 'hits', 'batting_average')
    list_filter = ('game__season',)
    search_fields = ('player__first_name', 'player__last_name')

class BattingStatLineInline(nested_admin.NestedTabularInline):
    model = BattingStatLine
    extra = 1
    autocomplete_fields = ['player']

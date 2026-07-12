from django.contrib import admin
from .models import Player, Roster

class RosterInline(admin.TabularInline):
    model = Roster
    extra = 1

@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ('last_name', 'first_name', 'jersey_number')
    search_fields = ('first_name', 'last_name')
    inlines = [RosterInline]

@admin.register(Roster)
class RosterAdmin(admin.ModelAdmin):
    list_display = ('player', 'team', 'season')
    list_filter = ('season', 'team')
from django.contrib import admin
from .models import Season, Team

@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    list_display = ('year', 'name')
    ordering = ('-year',)

@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)
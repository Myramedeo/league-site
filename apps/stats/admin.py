from django.contrib import admin
from .models import BattingStatLine, PitchingStatLine

admin.site.register(BattingStatLine)
admin.site.register(PitchingStatLine)
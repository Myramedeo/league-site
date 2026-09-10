from django.contrib import admin

from .models import Album, Photo


class PhotoInline(admin.TabularInline):
    model = Photo
    extra = 1
    fields = ('title', 'image', 'caption', 'active', 'order')


@admin.register(Album)
class AlbumAdmin(admin.ModelAdmin):
    list_display = ('name', 'active', 'order', 'created_at')
    list_filter = ('active',)
    search_fields = ('name', 'description')
    inlines = [PhotoInline]


@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = ('title', 'album', 'active', 'order', 'created_at')
    list_filter = ('active', 'album')
    search_fields = ('title', 'caption')
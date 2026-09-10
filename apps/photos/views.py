from django.db import models
from django.shortcuts import render

from .models import Album, Photo


def photo_list(request):
    albums = (
        Album.objects.filter(active=True)
        .prefetch_related(
            models.Prefetch(
                'photos', queryset=Photo.objects.filter(active=True), to_attr='active_photos'
            )
        )
    )
    albums = [album for album in albums if album.active_photos]

    unfiled_photos = Photo.objects.filter(active=True, album__isnull=True)

    return render(
        request,
        'photos/photo_list.html',
        {'albums': albums, 'unfiled_photos': unfiled_photos},
    )
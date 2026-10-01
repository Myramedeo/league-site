from django.db import models

from core.image_utils import convert_heic_upload


class Album(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0, help_text='Lower numbers appear first.')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', '-created_at']

    def __str__(self):
        return self.name


class Photo(models.Model):
    album = models.ForeignKey(
        Album, on_delete=models.SET_NULL, null=True, blank=True, related_name='photos'
    )
    title = models.CharField(max_length=255)
    image = models.ImageField(upload_to='photos/%Y/%m/')
    caption = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0, help_text='Lower numbers appear first within an album.')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['album__order', 'order', '-created_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        convert_heic_upload(self.image)
        super().save(*args, **kwargs)
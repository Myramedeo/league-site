from django.utils import timezone
from django.db import models
from django.core.validators import FileExtensionValidator

from core.image_utils import convert_heic_upload


class Announcement(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    image = models.ImageField(
        upload_to='announcements/%Y/%m/',
        blank=True,
        null=True,
        help_text='Optional announcement image. HEIC/HEIF uploads are stored as JPEG.',
    )
    attachment = models.FileField(
        upload_to='announcements/%Y/%m/',
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=['docx'])],
        help_text='Optional Microsoft Word document (.docx).',
    )
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_recent(self):
        return self.created_at >= timezone.now() - timezone.timedelta(days=7)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        convert_heic_upload(self.image)
        super().save(*args, **kwargs)

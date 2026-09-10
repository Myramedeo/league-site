from django.db import models
from django.core.validators import FileExtensionValidator


class Announcement(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
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

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

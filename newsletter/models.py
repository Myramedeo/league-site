from django.db import models
from uuid import uuid4


class NewsletterSubscriber(models.Model):
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=False)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmation_token = models.UUIDField(default=uuid4, unique=True, editable=False)
    unsubscribe_token = models.UUIDField(default=uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.email

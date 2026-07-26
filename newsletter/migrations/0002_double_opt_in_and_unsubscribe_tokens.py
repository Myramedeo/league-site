from uuid import uuid4

from django.db import migrations, models
from django.utils import timezone


def mark_existing_active_as_confirmed(apps, schema_editor):
    NewsletterSubscriber = apps.get_model('newsletter', 'NewsletterSubscriber')
    NewsletterSubscriber.objects.filter(is_active=True, confirmed_at__isnull=True).update(
        confirmed_at=timezone.now()
    )


class Migration(migrations.Migration):
    dependencies = [
        ('newsletter', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='newslettersubscriber',
            name='confirmation_token',
            field=models.UUIDField(default=uuid4, editable=False, unique=True),
        ),
        migrations.AddField(
            model_name='newslettersubscriber',
            name='confirmed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='newslettersubscriber',
            name='unsubscribe_token',
            field=models.UUIDField(default=uuid4, editable=False, unique=True),
        ),
        migrations.AlterField(
            model_name='newslettersubscriber',
            name='is_active',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(mark_existing_active_as_confirmed, migrations.RunPython.noop),
    ]

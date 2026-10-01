from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('announcements', '0002_announcement_attachment'),
    ]

    operations = [
        migrations.AddField(
            model_name='announcement',
            name='image',
            field=models.ImageField(
                blank=True,
                help_text='Optional announcement image. HEIC/HEIF uploads are stored as JPEG.',
                null=True,
                upload_to='announcements/%Y/%m/',
            ),
        ),
    ]
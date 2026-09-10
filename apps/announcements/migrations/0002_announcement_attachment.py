from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('announcements', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='announcement',
            name='attachment',
            field=models.FileField(
                blank=True,
                help_text='Optional Microsoft Word document (.docx).',
                null=True,
                upload_to='announcements/%Y/%m/',
                validators=[django.core.validators.FileExtensionValidator(allowed_extensions=['docx'])],
            ),
        ),
    ]
from django.core.validators import MinLengthValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('teams', '0002_competition_legacyteamidentity'),
    ]

    operations = [
        migrations.AddField(
            model_name='team',
            name='abbreviation',
            field=models.CharField(blank=True, max_length=4, validators=[MinLengthValidator(3)]),
        ),
    ]
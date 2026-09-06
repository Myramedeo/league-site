# Generated for the simplified play-cell model (no base/runner tracking).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game_entry', '0007_alter_scorecardentry_result'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='scorecardentry',
            name='batter_ending_base',
        ),
        migrations.RemoveField(
            model_name='scorecardentry',
            name='runner_1st_before',
        ),
        migrations.RemoveField(
            model_name='scorecardentry',
            name='runner_1st_ending',
        ),
        migrations.RemoveField(
            model_name='scorecardentry',
            name='runner_2nd_before',
        ),
        migrations.RemoveField(
            model_name='scorecardentry',
            name='runner_2nd_ending',
        ),
        migrations.RemoveField(
            model_name='scorecardentry',
            name='runner_3rd_before',
        ),
        migrations.RemoveField(
            model_name='scorecardentry',
            name='runner_3rd_ending',
        ),
        migrations.AddField(
            model_name='scorecardentry',
            name='scored',
            field=models.BooleanField(default=False),
        ),
    ]

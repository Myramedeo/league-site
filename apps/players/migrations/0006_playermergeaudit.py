from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('players', '0005_roster_show_in_team_list'),
    ]

    operations = [
        migrations.CreateModel(
            name='PlayerMergeAudit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source_player_id', models.PositiveBigIntegerField()),
                ('target_name', models.CharField(max_length=101)),
                ('source_name', models.CharField(max_length=101)),
                ('before_state', models.JSONField()),
                ('after_state', models.JSONField()),
                ('merged_at', models.DateTimeField(auto_now_add=True)),
                ('undone_at', models.DateTimeField(blank=True, null=True)),
                ('merged_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='player_merges', to=settings.AUTH_USER_MODEL)),
                ('target_player', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='merge_targets', to='players.player')),
            ],
            options={'ordering': ['-merged_at']},
        ),
    ]
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from core.imports.legacy_csv import _parse_score, validate_source


class LegacyCsvValidationTests(SimpleTestCase):
    def test_parses_legacy_final_score_in_visitor_home_order(self):
        self.assertEqual(
            _parse_score('F 4-14'),
            {'away_score': 4, 'home_score': 14},
        )

    def test_validates_repository_export_shape(self):
        report = validate_source(Path(settings.BASE_DIR) / 'old_data')

        self.assertEqual(report.counts['divisions.csv'], 17)
        self.assertEqual(report.counts['game_ids.csv'], 326)
        self.assertFalse(report.errors)
        self.assertTrue(any('off-day' in item.message for item in report.diagnostics))
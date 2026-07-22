from django.test import TestCase
from .models import Announcement


class AnnouncementTests(TestCase):
    def setUp(self):
        self.announcement = Announcement.objects.create(
            title="Test Announcement",
            description="This is a test announcement",
            active=True
        )

    def test_announcement_creation(self):
        self.assertEqual(self.announcement.title, "Test Announcement")
        self.assertEqual(self.announcement.description, "This is a test announcement")
        self.assertTrue(self.announcement.active)

    def test_announcement_str(self):
        self.assertEqual(str(self.announcement), "Test Announcement")

    def test_inactive_announcements_excluded(self):
        inactive = Announcement.objects.create(
            title="Inactive",
            description="Inactive announcement",
            active=False
        )
        # Only active announcements should be returned by default query
        active_announcements = Announcement.objects.filter(active=True)
        self.assertIn(self.announcement, active_announcements)
        self.assertNotIn(inactive, active_announcements)

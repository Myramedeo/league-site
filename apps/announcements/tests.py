from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from announcements.models import Announcement


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

    def test_docx_attachment_is_stored(self):
        announcement = Announcement.objects.create(
            title='Document',
            description='Attached document',
            attachment=SimpleUploadedFile(
                'league-notice.docx',
                b'not a real document for this storage test',
                content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            ),
        )

        self.assertTrue(announcement.attachment.name.startswith('announcements/'))
        self.assertTrue(announcement.attachment.name.endswith('.docx'))

    def test_only_docx_attachments_are_valid(self):
        announcement = Announcement(
            title='Invalid document',
            description='Invalid attachment',
            attachment=SimpleUploadedFile('league-notice.pdf', b'pdf'),
        )

        with self.assertRaises(ValidationError):
            announcement.full_clean()

    def test_homepage_renders_attachment_link(self):
        self.announcement.attachment = SimpleUploadedFile('league-notice.docx', b'document')
        self.announcement.save()

        response = self.client.get(reverse('home'))

        self.assertContains(response, 'Download attached document')
        self.assertContains(response, announcement_attachment_name := self.announcement.attachment.name)

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

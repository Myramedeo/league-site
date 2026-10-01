from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image
from announcements.models import Announcement


@override_settings(
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    }
)
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

    def test_heic_image_is_validated_stored_as_jpeg_and_rendered_above_text(self):
        heic_data = BytesIO()
        Image.new('RGB', (1, 1), color='red').save(heic_data, format='HEIF')
        announcement = Announcement(
            title='Photo announcement',
            description='Announcement text below the image.',
            image=SimpleUploadedFile(
                'league-event.HEIC', heic_data.getvalue(), content_type='image/heic'
            ),
        )

        announcement.full_clean()
        announcement.save()

        self.assertTrue(announcement.image.name.endswith('.jpg'))
        with Image.open(announcement.image) as stored_image:
            self.assertEqual(stored_image.format, 'JPEG')

        response = self.client.get(reverse('home'))
        rendered_content = response.content.decode()
        self.assertLess(
            rendered_content.index(announcement.image.url),
            rendered_content.index(announcement.description),
        )

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

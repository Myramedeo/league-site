from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from photos.models import Photo


@override_settings(
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    }
)
class PhotoListTests(TestCase):
    def test_photo_list_only_shows_active_photos(self):
        active_photo = Photo.objects.create(
            title='Opening Day', image='photos/opening-day.jpg'
        )
        Photo.objects.create(title='Archived Photo', image='photos/archived.jpg', active=False)

        response = self.client.get(reverse('photo_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, active_photo.title)
        self.assertNotContains(response, 'Archived Photo')

    def test_heic_photo_upload_is_stored_as_jpeg(self):
        heic_data = BytesIO()
        Image.new('RGB', (1, 1), color='red').save(heic_data, format='HEIF')
        uploaded_image = SimpleUploadedFile(
            'opening-day.HEIC', heic_data.getvalue(), content_type='image/heic'
        )
        photo = Photo(title='Opening Day', image=uploaded_image)

        photo.full_clean()
        photo.save()

        self.assertTrue(photo.image.name.endswith('.jpg'))
        with Image.open(photo.image) as stored_image:
            self.assertEqual(stored_image.format, 'JPEG')
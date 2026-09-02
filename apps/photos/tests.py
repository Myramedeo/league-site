from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Photo


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
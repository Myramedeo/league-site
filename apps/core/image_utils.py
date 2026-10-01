from io import BytesIO
from pathlib import Path

from django.core.files.base import ContentFile
from PIL import Image


def convert_heic_upload(image):
    if (
        image
        and not image._committed
        and Path(image.name).suffix.lower() in {'.heic', '.heif'}
    ):
        with Image.open(image) as source:
            output = BytesIO()
            source.convert('RGB').save(output, format='JPEG', quality=90)

        filename = f'{Path(image.name).stem}.jpg'
        image.save(filename, ContentFile(output.getvalue()), save=False)
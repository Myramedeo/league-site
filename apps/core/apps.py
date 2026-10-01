from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = 'core'

    def ready(self):
        from pillow_heif import register_heif_opener

        register_heif_opener()

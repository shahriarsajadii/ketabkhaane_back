from django.apps import AppConfig


class AuthorsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "authors"

    def ready(self):
        from core.images import make_delete_image_receiver

        from .models import Author

        make_delete_image_receiver(Author)

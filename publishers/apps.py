from django.apps import AppConfig

class PublishersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "publishers"

    def ready(self):
        from core.images import make_delete_image_receiver

        from .models import Publisher

        make_delete_image_receiver(Publisher)

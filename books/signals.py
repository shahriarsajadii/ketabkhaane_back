from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Book


@receiver(post_delete, sender=Book)
def delete_book_image_file(sender, instance, **kwargs):
    """با حذف کتاب فایل عکسش هم از دیسک پاک شود."""
    if instance.image:
        instance.image.delete(save=False)

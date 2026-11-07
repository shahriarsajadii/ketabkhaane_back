from django.db import models

from core.models import BaseModel
from core.utils import random_image_path


def publisher_image_path(instance, filename):
    return random_image_path("publishers", filename)


class Publisher(BaseModel):
    name = models.CharField("نام ناشر", max_length=255, unique=True)
    image = models.ImageField("عکس", upload_to=publisher_image_path, null=True, blank=True)

    class Meta:
        db_table = "publishers"
        ordering = ["name"]
        verbose_name = "ناشر"
        verbose_name_plural = "ناشران"

    def __str__(self):
        return self.name

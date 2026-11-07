from django.db import models

from core.models import BaseModel
from core.utils import random_image_path


def author_image_path(instance, filename):
    return random_image_path("authors", filename)


class Author(BaseModel):
    name = models.CharField("نام نویسنده", max_length=255, unique=True)
    description = models.TextField("توضیحات", blank=True, default="")
    image = models.ImageField("عکس", upload_to=author_image_path, null=True, blank=True)

    class Meta:
        db_table = "authors"
        ordering = ["name"]
        verbose_name = "نویسنده"
        verbose_name_plural = "نویسنده‌ها"

    def __str__(self):
        return self.name

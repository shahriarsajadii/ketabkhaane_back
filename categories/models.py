from django.db import models

from core.models import BaseModel


class Category(BaseModel):
    title = models.CharField(max_length=100, unique=True)

    class Meta:
        db_table = "categories"
        ordering = ["title"]
        verbose_name = "دسته‌بندی"
        verbose_name_plural = "دسته‌بندی‌ها"

    def __str__(self):
        return self.title

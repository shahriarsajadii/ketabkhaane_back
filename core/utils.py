import os
import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone


def random_image_path(folder, filename):
    """اسم فایل را رندوم می‌کنیم تا اسم فارسی/تکراری مشکلی نسازد. (در upload_to مدل‌ها استفاده می‌شود)"""
    ext = os.path.splitext(filename)[1].lower() or ".jpg"
    return f"{folder}/{timezone.now():%Y/%m}/{uuid.uuid4().hex}{ext}"


def get_object(queryset, param, fields=("id",)):
    """
    اولین رکوردی که با یکی از فیلدها (به ترتیب) با param برابر باشد را برمی‌گرداند.
    اگر پیدا نشد None.
    """
    for field in fields:
        try:
            obj = queryset.filter(**{field: param}).first()
        except (ValueError, TypeError, DjangoValidationError):
            continue
        if obj is not None:
            return obj
    return None

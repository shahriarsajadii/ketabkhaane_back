"""
ابزارهای مشترک آپلود عکس (ناشر، نویسنده، ...).

هر مدل فقط یک تابع upload_to ساده می‌نویسد (با core.utils.random_image_path؛ چون migration ها
باید به آن اشاره کنند)، و بقیه‌ی کار (اعتبارسنجی عکس، آپلود/حذف، آدرس کامل عکس) اینجاست.
"""
from django.conf import settings
from rest_framework import serializers
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.views import APIView

from core.utils import get_object


class ImageUrlMixin:
    def get_image(self, obj):
        if not obj.image:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(obj.image.url) if request else obj.image.url


class ImageUploadSerializer(serializers.Serializer):
    image = serializers.ImageField(error_messages={
        "required": "فایل عکس ارسال نشده است.",
        "invalid_image": "فایل ارسال‌شده یک عکس معتبر نیست.",
        "empty": "فایل خالی است.",
    })

    def validate_image(self, value):
        limit = settings.BOOK_IMAGE_MAX_MB
        if value.size > limit * 1024 * 1024:
            raise serializers.ValidationError(f"حجم عکس نباید بیشتر از {limit} مگابایت باشد.")
        return value


class ImageUploadView(APIView):
    """
    POST   .../<id>/image/   (multipart: image=<file>)  → آپلود یا جایگزینی
    DELETE .../<id>/image/                              → حذف عکس

    در زیرکلاس‌ها تعیین کن: model، response_helper، permission_classes، permission_by_method
    """
    model = None
    response_helper = None
    parser_classes = [MultiPartParser, FormParser]

    def _get(self, param):
        return get_object(self.model.objects.all(), param)

    @staticmethod
    def _image_url(request, obj):
        return request.build_absolute_uri(obj.image.url) if obj.image else None

    def post(self, request, param):
        obj = self._get(param)
        if obj is None:
            return self.response_helper.not_found_response()

        serializer = ImageUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        old_name = obj.image.name if obj.image else None
        obj.image = serializer.validated_data["image"]
        obj.updated_by = request.user
        obj.save()

        # فایل قبلی را بعد از ذخیره‌ی موفق پاک می‌کنیم
        if old_name and old_name != obj.image.name:
            obj.image.storage.delete(old_name)

        return self.response_helper.success_update_response(
            message="عکس ذخیره شد.",
            data={"image": self._image_url(request, obj)},
        )

    def delete(self, request, param):
        obj = self._get(param)
        if obj is None:
            return self.response_helper.not_found_response()

        if obj.image:
            obj.image.delete(save=False)
            obj.image = None
            obj.updated_by = request.user
            obj.save()
        return self.response_helper.success_delete_response(message="عکس حذف شد.")


def make_delete_image_receiver(model):
    """با حذف رکورد (تکی یا گروهی) فایل عکسش هم از دیسک پاک شود."""
    from django.db.models.signals import post_delete

    def _delete_file(sender, instance, **kwargs):
        if instance.image:
            instance.image.delete(save=False)

    post_delete.connect(_delete_file, sender=model, weak=False, dispatch_uid=f"delete_image_{model._meta.label}")

from rest_framework import serializers

from core.images import ImageUrlMixin
from .models import Author


class AuthorSerializer(ImageUrlMixin, serializers.ModelSerializer):
    books_count = serializers.IntegerField(read_only=True, default=0)
    image = serializers.SerializerMethodField()

    class Meta:
        model = Author
        fields = ["id", "name", "description", "image", "books_count", "created_at", "updated_at"]
        read_only_fields = fields


class AuthorCreateUpdateSerializer(serializers.ModelSerializer):
    name = serializers.CharField(max_length=255, error_messages={
        "required": "نام نویسنده الزامی است.",
        "blank": "نام نویسنده نمی‌تواند خالی باشد.",
        "max_length": "نام نویسنده نباید بیشتر از ۲۵۵ کاراکتر باشد.",
    })
    # اختیاری
    description = serializers.CharField(required=False, allow_blank=True, default="")

    class Meta:
        model = Author
        fields = ["id", "name", "description"]

    def validate_name(self, value):
        value = " ".join(value.split())  # فاصله‌های اضافی
        if not value:
            raise serializers.ValidationError("نام نویسنده نمی‌تواند خالی باشد.")
        qs = Author.objects.filter(name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("نویسنده‌ای با این نام وجود دارد.")
        return value

    def validate_description(self, value):
        return (value or "").strip()

    def to_representation(self, instance):
        return AuthorSerializer(instance, context=self.context).data


class AuthorBulkDeleteSerializer(serializers.Serializer):
    items = serializers.ListField(
        child=serializers.PrimaryKeyRelatedField(
            queryset=Author.objects.all(),
            error_messages={"does_not_exist": "نویسنده با این شناسه یافت نشد."},
        ),
        allow_empty=False,
    )

    def validate_items(self, authors):
        used = [a.name for a in authors if a.books.exists()]
        if used:
            preview = "، ".join(used[:3]) + (" و ..." if len(used) > 3 else "")
            raise serializers.ValidationError(
                f"این نویسنده ‌ها کتاب دارند و حذف نمی‌ شوند: {preview}. ابتدا کتاب ‌هایشان را ویرایش یا حذف کنید."
            )
        return authors

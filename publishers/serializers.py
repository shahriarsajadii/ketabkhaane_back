from rest_framework import serializers

from core.images import ImageUrlMixin

from .models import Publisher


class PublisherSerializer(ImageUrlMixin, serializers.ModelSerializer):
    books_count = serializers.IntegerField(read_only=True, default=0)
    image = serializers.SerializerMethodField()

    class Meta:
        model = Publisher
        fields = ["id", "name", "image", "books_count", "created_at", "updated_at"]
        read_only_fields = fields


class PublisherCreateUpdateSerializer(serializers.ModelSerializer):
    name = serializers.CharField(max_length=255, error_messages={
        "required": "نام ناشر الزامی است.",
        "blank": "نام ناشر نمی‌تواند خالی باشد.",
        "max_length": "نام ناشر نباید بیشتر از ۲۵۵ کاراکتر باشد.",
    })

    class Meta:
        model = Publisher
        fields = ["id", "name"]

    def validate_name(self, value):
        value = " ".join(value.split())  # فاصله‌های اضافی
        if not value:
            raise serializers.ValidationError("نام ناشر نمی‌تواند خالی باشد.")
        qs = Publisher.objects.filter(name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("ناشری با این نام وجود دارد.")
        return value

    def to_representation(self, instance):
        return PublisherSerializer(instance, context=self.context).data


class PublisherBulkDeleteSerializer(serializers.Serializer):
    items = serializers.ListField(
        child=serializers.PrimaryKeyRelatedField(
            queryset=Publisher.objects.all(),
            error_messages={"does_not_exist": "ناشر با این شناسه یافت نشد."},
        ),
        allow_empty=False,
    )

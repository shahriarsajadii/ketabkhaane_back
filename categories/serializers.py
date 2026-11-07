from rest_framework import serializers

from .models import Category


class CategorySerializer(serializers.ModelSerializer):
    books_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Category
        fields = ["id", "title", "books_count", "created_at"]
        read_only_fields = fields


class CategoryCreateUpdateSerializer(serializers.ModelSerializer):
    title = serializers.CharField(max_length=100, error_messages={
        "required": "عنوان دسته‌بندی الزامی است.",
        "blank": "عنوان دسته‌بندی نمی‌تواند خالی باشد.",
    })

    class Meta:
        model = Category
        fields = ["id", "title"]

    def validate_title(self, value):
        value = " ".join(value.split())  # فاصله‌های اضافی
        qs = Category.objects.filter(title__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("دسته‌بندی‌ای با این عنوان وجود دارد.")
        return value

    def to_representation(self, instance):
        return CategorySerializer(instance, context=self.context).data


class CategoryBulkDeleteSerializer(serializers.Serializer):
    items = serializers.ListField(
        child=serializers.PrimaryKeyRelatedField(
            queryset=Category.objects.all(),
            error_messages={"does_not_exist": "دسته‌بندی با این شناسه یافت نشد."},
        ),
        allow_empty=False,
    )

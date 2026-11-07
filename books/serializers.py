from django.conf import settings
from django.db import transaction
from rest_framework import serializers

from authors.models import Author
from categories.models import Category
from publishers.models import Publisher

from .addresses import normalize_address
from .models import Book
from .queries import book_queryset
from .services import sync_copies


# -------------------------------------------------
# خواندن
# -------------------------------------------------
class CategoryMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "title"]


class AuthorMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Author
        fields = ["id", "name"]


class PublisherMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Publisher
        fields = ["id", "name"]


class ImageUrlMixin:
    def get_image(self, obj):
        if not obj.image:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(obj.image.url) if request else obj.image.url


class BookListSerializer(ImageUrlMixin, serializers.ModelSerializer):
    count = serializers.SerializerMethodField()
    addresses = serializers.SerializerMethodField()
    categories = CategoryMiniSerializer(many=True, read_only=True)
    authors = AuthorMiniSerializer(many=True, read_only=True)
    publisher = PublisherMiniSerializer(read_only=True)
    image = serializers.SerializerMethodField()

    class Meta:
        model = Book
        fields = [
            "id", "title", "authors", "translator", "publisher", "publish_year",
            "isbn", "count", "addresses", "categories", "image",
            "print_series", "print_series_date", "dewey_classification",
            "national_bibliography_number", "circulation", "first_print_date",
        ]
        read_only_fields = fields

    def get_count(self, obj):
        return obj.count

    def get_addresses(self, obj):
        return [copy.address for copy in obj.copies.all()]


class BookDetailSerializer(BookListSerializer):
    created_by = serializers.SerializerMethodField()

    class Meta(BookListSerializer.Meta):
        fields = BookListSerializer.Meta.fields + ["note", "created_by", "created_at", "updated_at"]
        read_only_fields = fields

    def get_created_by(self, obj):
        return obj.created_by.name if obj.created_by else None


# -------------------------------------------------
# ساخت / ویرایش
# -------------------------------------------------
class BookCreateUpdateSerializer(serializers.ModelSerializer):
    """
    ورودی:
        {
          "title": "یادداشت‌های زیرزمینی",
          "authors": [3, 7], "translator": "...",      # شناسه‌ی نویسنده‌ها (حداقل یکی)
          "publisher": 2,                               # اختیاری؛ شناسه‌ی ناشر یا null
          "count": 3,                                   # اختیاری؛ پیش‌فرض = تعداد آدرس‌ها (حداقل 1)
          "addresses": ["01-05", "01-06", "02-10"],     # «قفسه-ردیف» (هرکدام ۱ تا ۵۰)، دقیقاً به تعداد نسخه‌ها
          "categories": [1, 4],                         # اختیاری
          "publish_year": 1398, "isbn": "", "note": ""
        }
    در PATCH: اگر addresses بیاید، کل لیست آدرس‌ها جایگزین می‌شود (به ترتیب).
    """

    count = serializers.IntegerField(required=False, min_value=1, error_messages={
        "min_value": "تعداد باید حداقل ۱ باشد.",
        "invalid": "تعداد باید یک عدد صحیح باشد.",
    })
    addresses = serializers.ListField(
        child=serializers.CharField(max_length=255, allow_blank=False, error_messages={
            "blank": "آدرس قفسه نمی‌تواند خالی باشد.",
            "max_length": "آدرس قفسه نباید بیشتر از ۲۵۵ کاراکتر باشد.",
        }),
        allow_empty=False,
        error_messages={
            "required": "آدرس قفسه الزامی است.",
            "empty": "حداقل یک آدرس قفسه وارد کنید.",
            "not_a_list": "آدرس‌ها باید به‌صورت لیست ارسال شوند.",
        },
    )
    categories = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Category.objects.all(),
        required=False,
        error_messages={"does_not_exist": "دسته‌بندی با این شناسه یافت نشد."},
    )
    authors = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Author.objects.all(),
        allow_empty=False,
        error_messages={
            "required": "نام نویسنده الزامی است.",
            "empty": "حداقل یک نویسنده انتخاب کنید.",
            "does_not_exist": "نویسنده با این شناسه یافت نشد.",
            "not_a_list": "نویسنده‌ها باید به‌صورت لیست ارسال شوند.",
        },
    )
    publisher = serializers.PrimaryKeyRelatedField(
        queryset=Publisher.objects.all(),
        required=False,
        allow_null=True,
        error_messages={"does_not_exist": "ناشر با این شناسه یافت نشد."},
    )

    class Meta:
        model = Book
        fields = [
            "id", "title", "authors", "translator", "count", "addresses",
            "publisher", "publish_year", "isbn", "note", "categories",
            "print_series", "print_series_date", "dewey_classification",
            "national_bibliography_number", "circulation", "first_print_date",
        ]
        extra_kwargs = {
            "title": {"error_messages": {"required": "نام کتاب الزامی است.", "blank": "نام کتاب نمی‌تواند خالی باشد."}},
        }

    # ---------- validation ----------
    def validate_publish_year(self, value):
        if value is not None and not (1 <= value <= 2100):
            raise serializers.ValidationError("سال انتشار معتبر نیست.")
        return value

    def validate_addresses(self, value):
        max_copies = settings.BOOK_MAX_COPIES
        if len(value) > max_copies:
            raise serializers.ValidationError(f"حداکثر {max_copies} نسخه از یک کتاب مجاز است.")

        # هر آدرس باید «قفسه-ردیف» باشد (مثلا 01-05) و به شکل استاندارد ذخیره می‌شود.
        # خطاها به‌صورت {index: [پیام]} برمی‌گردند تا فرم بداند کدام نسخه مشکل دارد.
        normalized, errors = [], {}
        for index, item in enumerate(value):
            try:
                normalized.append(normalize_address(item, settings.BOOK_SHELF_MAX, settings.BOOK_ROW_MAX))
            except ValueError as exc:
                errors[index] = [str(exc)]
        if errors:
            raise serializers.ValidationError(errors)
        return normalized

    def validate(self, attrs):
        instance = self.instance
        addresses = attrs.get("addresses")
        count = attrs.get("count")

        # --- تعداد ↔ آدرس‌ها ---
        if addresses is not None:
            if count is not None and count != len(addresses):
                raise serializers.ValidationError({
                    "addresses": [
                        f"تعداد آدرس‌ها ({len(addresses)}) با تعداد کتاب‌ها ({count}) برابر نیست. "
                        "برای هر نسخه یک آدرس وارد کنید."
                    ]
                })
        elif count is not None and instance is not None and count != len(instance.copies.all()):
            raise serializers.ValidationError({
                "addresses": ["برای تغییر تعداد، آدرس همه‌ی نسخه‌ها را هم ارسال کنید."]
            })

        # --- جلوگیری از ثبت تکراری ---
        # کتاب تکراری = همان نام، مترجم، ناشر و همان مجموعه‌ی نویسنده‌ها
        keys = ("title", "authors", "translator", "publisher")
        if instance is None or any(k in attrs for k in keys):
            def value_of(key):
                if key in attrs:
                    return attrs[key]
                if instance is None:
                    return [] if key == "authors" else ("" if key != "publisher" else None)
                if key == "authors":
                    return list(instance.authors.all())
                return getattr(instance, key)

            author_ids = {a.pk for a in value_of("authors")}
            publisher = value_of("publisher")
            candidates = Book.objects.filter(
                title__iexact=value_of("title"),
                translator__iexact=value_of("translator"),
                publisher=publisher,
            ).prefetch_related("authors")
            if instance:
                candidates = candidates.exclude(pk=instance.pk)
            if any({a.pk for a in book.authors.all()} == author_ids for book in candidates):
                raise serializers.ValidationError({
                    "title": [
                        "این کتاب (با همین نویسنده، مترجم و ناشر) قبلاً ثبت شده است. "
                        "اگر نسخه‌ی دیگری از آن دارید، تعداد و آدرس‌های همان کتاب را ویرایش کنید."
                    ]
                })
        return attrs

    # ---------- write ----------
    @transaction.atomic
    def create(self, validated_data):
        addresses = validated_data.pop("addresses")
        validated_data.pop("count", None)
        categories = validated_data.pop("categories", [])
        authors = validated_data.pop("authors")

        book = Book.objects.create(**validated_data)
        book.categories.set(categories)
        book.authors.set(authors)
        sync_copies(book, addresses)
        return book

    @transaction.atomic
    def update(self, instance, validated_data):
        addresses = validated_data.pop("addresses", None)
        validated_data.pop("count", None)
        categories = validated_data.pop("categories", None)
        authors = validated_data.pop("authors", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if categories is not None:
            instance.categories.set(categories)
        if authors is not None:
            instance.authors.set(authors)
        if addresses is not None:
            sync_copies(instance, addresses)
        return instance

    def to_representation(self, instance):
        # دوباره از دیتابیس می‌خوانیم تا آدرس‌ها/دسته‌های جدید (و نه cache قبلی) برگردند
        fresh = book_queryset().get(pk=instance.pk)
        return BookDetailSerializer(fresh, context=self.context).data


class BookBulkDeleteSerializer(serializers.Serializer):
    items = serializers.ListField(
        child=serializers.PrimaryKeyRelatedField(
            queryset=Book.objects.all(),
            error_messages={"does_not_exist": "کتابی با این شناسه یافت نشد."},
        ),
        allow_empty=False,
    )


# -------------------------------------------------
# آپلود فایل‌ها
# -------------------------------------------------
class BookImageSerializer(serializers.Serializer):
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


class ExcelUploadSerializer(serializers.Serializer):
    file = serializers.FileField(error_messages={
        "required": "فایل اکسل ارسال نشده است.",
        "empty": "فایل خالی است.",
    })

    def validate_file(self, value):
        if not value.name.lower().endswith(".xlsx"):
            raise serializers.ValidationError(
                "فقط فایل .xlsx پذیرفته می‌شود (اگر فایل .xls دارید در اکسل با Save As به xlsx تبدیلش کنید)."
            )
        limit = settings.BOOK_EXCEL_MAX_MB
        if value.size > limit * 1024 * 1024:
            raise serializers.ValidationError(f"حجم فایل نباید بیشتر از {limit} مگابایت باشد.")
        return value

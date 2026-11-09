from django.conf import settings
from django.db import transaction
from rest_framework import serializers

from authors.models import Author
from categories.models import Category
from publishers.models import Publisher

from .addresses import normalize_address
from .models import Book, BookSeries
from .queries import book_queryset
from .services import _get_or_create_categories, _get_or_create_named, _get_or_create_series, sync_copies


class CategoryMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "title"]


class BookSeriesSerializer(serializers.ModelSerializer):
    books_count = serializers.SerializerMethodField()

    class Meta:
        model = BookSeries
        fields = ["id", "title", "books_count", "created_at"]
        read_only_fields = fields

    def get_books_count(self, obj):
        return getattr(obj, "books_count", None) if hasattr(obj, "books_count") else obj.books.count()


class BookSeriesCreateUpdateSerializer(serializers.ModelSerializer):
    title = serializers.CharField(max_length=255, error_messages={
        "required": "نام مجموعه الزامی است.",
        "blank": "نام مجموعه نمی‌تواند خالی باشد.",
    })

    class Meta:
        model = BookSeries
        fields = ["id", "title"]

    def validate_title(self, value):
        value = " ".join(value.split())
        qs = BookSeries.objects.filter(title__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("مجموعه‌ای با این نام وجود دارد.")
        return value

    def to_representation(self, instance):
        return BookSeriesSerializer(instance, context=self.context).data


class BookSeriesBulkDeleteSerializer(serializers.Serializer):
    items = serializers.ListField(
        child=serializers.PrimaryKeyRelatedField(
            queryset=BookSeries.objects.all(),
            error_messages={"does_not_exist": "مجموعه‌ای با این شناسه یافت نشد."},
        ),
        allow_empty=False,
    )


class BookCopySerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    address = serializers.CharField()
    is_loaned = serializers.BooleanField()
    loaned_to = serializers.CharField()


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
    copies = serializers.SerializerMethodField()
    categories = CategoryMiniSerializer(many=True, read_only=True)
    authors = AuthorMiniSerializer(many=True, read_only=True)
    publisher = PublisherMiniSerializer(read_only=True)
    series = BookSeriesSerializer(read_only=True)
    image = serializers.SerializerMethodField()

    class Meta:
        model = Book
        fields = [
            "id", "title", "authors", "translator", "publisher", "publish_year",
            "isbn", "page_count", "count", "addresses", "copies", "categories", "image",
            "subject", "series", "volume_number",
            "print_series", "print_series_date", "dewey_classification",
            "national_bibliography_number", "circulation", "first_print_date",
        ]
        read_only_fields = fields

    def get_count(self, obj):
        return obj.count

    def get_addresses(self, obj):
        return [copy.address for copy in obj.copies.all()]

    def get_copies(self, obj):
        return [
            {
                "id": copy.id,
                "address": copy.address,
                "is_loaned": copy.is_loaned,
                "loaned_to": copy.loaned_to,
            }
            for copy in obj.copies.all()
        ]


class BookDetailSerializer(BookListSerializer):
    created_by = serializers.SerializerMethodField()

    class Meta(BookListSerializer.Meta):
        fields = BookListSerializer.Meta.fields + ["note", "created_by", "created_at", "updated_at"]
        read_only_fields = fields

    def get_created_by(self, obj):
        return obj.created_by.name if obj.created_by else None


class BookCreateUpdateSerializer(serializers.ModelSerializer):
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
        required=False,
        error_messages={
            "required": "آدرس قفسه الزامی است.",
            "empty": "حداقل یک آدرس قفسه وارد کنید.",
            "not_a_list": "آدرس‌ها باید به‌صورت لیست ارسال شوند.",
        },
    )

    copies = serializers.ListField(
        child=serializers.DictField(), required=False, allow_empty=False, write_only=True,
        error_messages={
            "empty": "حداقل یک نسخه وارد کنید.",
            "not_a_list": "نسخه‌ها باید به‌صورت لیست ارسال شوند.",
        },
    )
    series = serializers.PrimaryKeyRelatedField(
        queryset=BookSeries.objects.all(),
        required=False,
        allow_null=True,
        error_messages={"does_not_exist": "مجموعه‌ای با این شناسه یافت نشد."},
    )
    new_series = serializers.CharField(
        max_length=255, required=False, allow_blank=True, write_only=True,
        error_messages={"max_length": "نام مجموعه نباید بیشتر از ۲۵۵ کاراکتر باشد."},
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
        required=False,
        allow_empty=True,
        error_messages={
            "does_not_exist": "نویسنده با این شناسه یافت نشد.",
            "not_a_list": "نویسنده‌ها باید به‌صورت لیست ارسال شوند.",
        },
    )
    new_authors = serializers.ListField(
        child=serializers.CharField(max_length=255, allow_blank=False, error_messages={
            "max_length": "نام نویسنده نباید بیشتر از ۲۵۵ کاراکتر باشد.",
        }),
        required=False,
        write_only=True,
    )
    new_publisher = serializers.CharField(
        max_length=255, required=False, allow_blank=True, write_only=True,
        error_messages={"max_length": "نام ناشر نباید بیشتر از ۲۵۵ کاراکتر باشد."},
    )
    new_categories = serializers.ListField(
        child=serializers.CharField(max_length=100, allow_blank=False, error_messages={
            "max_length": "نام دسته‌بندی نباید بیشتر از ۱۰۰ کاراکتر باشد.",
        }),
        required=False,
        write_only=True,
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
            "id", "title", "authors", "translator", "count", "addresses", "copies",
            "publisher", "publish_year", "isbn", "page_count", "note", "categories",
            "subject", "series", "new_series", "volume_number",
            "new_authors", "new_publisher", "new_categories",
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

    def validate_page_count(self, value):
        if value is not None and not (1 <= value <= 100000):
            raise serializers.ValidationError("تعداد صفحه معتبر نیست.")
        return value

    @staticmethod
    def _clean_names(names):
        seen, result = set(), []
        for name in names or []:
            name = " ".join(str(name).split())
            if name and name.lower() not in seen:
                seen.add(name.lower())
                result.append(name)
        return result

    def _resolve_new_entities(self, attrs):
        instance = self.instance

        # ---- نویسنده‌ها ----
        if "new_authors" in attrs:
            names = self._clean_names(attrs.pop("new_authors"))
            if "authors" in attrs or instance is None:
                base = list(attrs.get("authors", []))
            else:
                base = list(instance.authors.all())
            missing = []
            for name in names:
                found = Author.objects.filter(name__iexact=name).first()
                if found is None:
                    missing.append(name)
                elif found not in base:
                    base.append(found)
            attrs["authors"] = base
            attrs["_new_author_names"] = missing

        # ---- ناشر ----
        if "new_publisher" in attrs:
            name = " ".join((attrs.pop("new_publisher") or "").split())
            if name and not attrs.get("publisher"):
                found = Publisher.objects.filter(name__iexact=name).first()
                if found:
                    attrs["publisher"] = found
                else:
                    attrs["_new_publisher_name"] = name

        # ---- مجموعه ----
        if "new_series" in attrs:
            name = " ".join((attrs.pop("new_series") or "").split())
            if name and not attrs.get("series"):
                found = BookSeries.objects.filter(title__iexact=name).first()
                if found:
                    attrs["series"] = found
                else:
                    attrs["_new_series_name"] = name

        # ---- دسته‌بندی‌ها ----
        if "new_categories" in attrs:
            names = self._clean_names(attrs.pop("new_categories"))
            if "categories" in attrs or instance is None:
                base = list(attrs.get("categories", []))
            else:
                base = list(instance.categories.all())
            missing = []
            for name in names:
                found = Category.objects.filter(title__iexact=name).first()
                if found is None:
                    missing.append(name)
                elif found not in base:
                    base.append(found)
            attrs["categories"] = base
            attrs["_new_category_names"] = missing

    def _normalize_one_address(self, index, address, errors):
        try:
            return normalize_address(address, settings.BOOK_SHELF_MAX, settings.BOOK_ROW_MAX)
        except ValueError as exc:
            errors[index] = [str(exc)]
            return address

    def validate_addresses(self, value):
        max_copies = settings.BOOK_MAX_COPIES
        if len(value) > max_copies:
            raise serializers.ValidationError(f"حداکثر {max_copies} نسخه از یک کتاب مجاز است.")

        # هر آدرس باید «قفسه-ردیف» باشه (مثلا 01-05) و به شکل استاندارد ذخیره میشه.
        normalized, errors = [], {}
        for index, item in enumerate(value):
            normalized.append(self._normalize_one_address(index, item, errors))
        if errors:
            raise serializers.ValidationError(errors)
        return normalized

    def validate_copies(self, value):
        max_copies = settings.BOOK_MAX_COPIES
        if len(value) > max_copies:
            raise serializers.ValidationError(f"حداکثر {max_copies} نسخه از یک کتاب مجاز است.")

        normalized, errors = [], {}
        for index, item in enumerate(value):
            if not isinstance(item, dict) or not item.get("address"):
                errors[index] = ["آدرس قفسه الزامی است."]
                continue
            address = self._normalize_one_address(index, item.get("address"), errors)
            is_loaned = bool(item.get("is_loaned", False))
            loaned_to = " ".join(str(item.get("loaned_to") or "").split())
            if is_loaned and not loaned_to:
                errors.setdefault(index, []).append(
                    "برای نسخه‌ی امانت داده‌شده، نام امانت‌گیرنده را وارد کنید."
                )
            if not is_loaned:
                loaned_to = ""
            normalized.append({"address": address, "is_loaned": is_loaned, "loaned_to": loaned_to})
        if errors:
            raise serializers.ValidationError(errors)
        return normalized

    def validate(self, attrs):
        instance = self.instance
        copies = attrs.get("copies")
        addresses = attrs.get("addresses")
        count = attrs.get("count")

        # اگر هر دو بیایند، copies (کامل‌تر) اولویت دارد و addresses نادیده گرفته می‌شود
        if copies is not None and addresses is not None:
            attrs.pop("addresses")
            addresses = None
        effective_len = len(copies) if copies is not None else (len(addresses) if addresses is not None else None)

        if instance is None and copies is None and addresses is None:
            raise serializers.ValidationError({"addresses": ["آدرس قفسه الزامی است."]})

        # --- موجودیت‌های جدید + حداقل یک نویسنده ---
        self._resolve_new_entities(attrs)
        authors_touched = "authors" in attrs
        if instance is None or authors_touched:
            if not attrs.get("authors") and not attrs.get("_new_author_names"):
                message = "حداقل یک نویسنده انتخاب کنید." if authors_touched else "نام نویسنده الزامی است."
                raise serializers.ValidationError({"authors": [message]})

        # --- تعداد ↔ آدرس‌ها/نسخه‌ها ---
        if effective_len is not None:
            if count is not None and count != effective_len:
                field = "copies" if copies is not None else "addresses"
                raise serializers.ValidationError({
                    field: [
                        f"تعداد نسخه‌ها ({effective_len}) با تعداد کتاب‌ها ({count}) برابر نیست. "
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
        # اگر نویسنده/ناشر کاملاً جدید است، کتابِ تکراری نمی‌تواند وجود داشته باشد
        has_new_entity = bool(attrs.get("_new_author_names") or attrs.get("_new_publisher_name"))
        if not has_new_entity and (instance is None or any(k in attrs for k in keys)):
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
    @staticmethod
    def _create_new_entities(validated_data, user):
        """نویسنده/ناشر/دسته‌ی جدید را می‌سازد (داخل transaction کتاب) و خروجی می‌دهد."""
        new_authors = _get_or_create_named(
            Author, "name", validated_data.pop("_new_author_names", []), user, "authors", "نویسنده"
        )
        publisher_name = validated_data.pop("_new_publisher_name", "")
        new_publisher = (
            _get_or_create_named(Publisher, "name", [publisher_name], user, "new_publisher", "ناشر")[0]
            if publisher_name else None
        )
        new_categories = _get_or_create_categories(validated_data.pop("_new_category_names", []), user)

        new_series_name = validated_data.pop("_new_series_name", "")
        new_series = _get_or_create_series(new_series_name, user) if new_series_name else None

        return new_authors, new_publisher, new_categories, new_series

    @transaction.atomic
    def create(self, validated_data):
        copies_data = validated_data.pop("copies", None)
        addresses = validated_data.pop("addresses", None)
        validated_data.pop("count", None)
        categories = validated_data.pop("categories", [])
        authors = validated_data.pop("authors", [])

        new_authors, new_publisher, new_categories, new_series = self._create_new_entities(
            validated_data, validated_data.get("created_by")
        )
        authors = [*authors, *new_authors]
        categories = [*categories, *new_categories]
        if new_publisher:
            validated_data["publisher"] = new_publisher
        if new_series:
            validated_data["series"] = new_series

        book = Book.objects.create(**validated_data)
        book.categories.set(categories)
        book.authors.set(authors)
        sync_copies(book, copies_data if copies_data is not None else addresses)
        return book

    @transaction.atomic
    def update(self, instance, validated_data):
        copies_data = validated_data.pop("copies", None)
        addresses = validated_data.pop("addresses", None)
        validated_data.pop("count", None)
        categories = validated_data.pop("categories", None)
        authors = validated_data.pop("authors", None)

        new_authors, new_publisher, new_categories, new_series = self._create_new_entities(
            validated_data, validated_data.get("updated_by")
        )
        if authors is not None:
            authors = [*authors, *new_authors]
        if categories is not None:
            categories = [*categories, *new_categories]
        if new_publisher:
            validated_data["publisher"] = new_publisher
        if new_series:
            validated_data["series"] = new_series

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if categories is not None:
            instance.categories.set(categories)
        if authors is not None:
            instance.authors.set(authors)
        copies_input = copies_data if copies_data is not None else addresses
        if copies_input is not None:
            sync_copies(instance, copies_input)
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
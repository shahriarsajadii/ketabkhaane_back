from django.conf import settings
from django.db import transaction
from rest_framework import serializers

from authors.models import Author
from categories.models import Category
from core.exceptions import APIError, flatten_errors
from publishers.models import Publisher

from .excel import ExcelImportError, parse_workbook
from .models import BookCopy


def sync_copies(book, addresses):
    """
    لیست آدرس‌های کتاب را با لیست جدید هماهنگ می‌کند (به ترتیب):
    آدرس‌های موجود ویرایش می‌شوند، اضافه‌ها ساخته و مازادها حذف می‌شوند.
    """
    existing = list(book.copies.order_by("id"))

    for copy, address in zip(existing, addresses):
        if copy.address != address:
            copy.address = address
            copy.save(update_fields=["address", "updated_at"])

    new_addresses = addresses[len(existing):]
    if new_addresses:
        BookCopy.objects.bulk_create([BookCopy(book=book, address=a) for a in new_addresses])

    for copy in existing[len(addresses):]:
        copy.delete()


def _get_or_create_categories(names, user):
    categories = []
    for name in names:
        name = " ".join(name.split())
        if len(name) > 100:
            raise serializers.ValidationError({"categories": [f"نام دسته‌بندی «{name[:30]}…» بیشتر از ۱۰۰ کاراکتر است."]})
        category = Category.objects.filter(title__iexact=name).first()
        if category is None:
            category = Category.objects.create(title=name, created_by=user, updated_by=user)
        categories.append(category)
    return categories


def _get_or_create_named(model, field, names, user, error_key, label):
    """Author/Publisher را با نام (بدون حساسیت به بزرگی/کوچکی حروف) پیدا یا می‌سازد."""
    result = []
    for name in names:
        name = " ".join(name.split())
        if len(name) > 255:
            raise serializers.ValidationError({error_key: [f"نام {label} «{name[:30]}…» بیشتر از ۲۵۵ کاراکتر است."]})
        obj = model.objects.filter(**{f"{field}__iexact": name}).first()
        if obj is None:
            obj = model.objects.create(**{field: name}, created_by=user, updated_by=user)
        result.append(obj)
    return result


def import_books_from_excel(content: bytes, user, skip_invalid: bool = False) -> dict:
    """
    ردیف‌های فایل اکسل را با همان سریالایزر API اعتبارسنجی و ثبت می‌کند.

    - skip_invalid=False (پیش‌فرض): اگر حتی یک ردیف خطا داشته باشد، هیچ‌چیز ثبت نمی‌شود.
    - skip_invalid=True: ردیف‌های سالم ثبت و ردیف‌های خراب گزارش می‌شوند.

    خروجی: {"total": n, "created": n, "failed": [{"row": 5, "title": "...", "errors": {...}}]}
    """
    # import محلی تا بین serializers ↔ services چرخه‌ی import نشود
    from .serializers import BookCreateUpdateSerializer

    try:
        rows = parse_workbook(
            content,
            max_rows=settings.BOOK_EXCEL_MAX_ROWS,
            max_copies=settings.BOOK_MAX_COPIES,
        )
    except ExcelImportError as exc:
        raise APIError(field="file", errors=[str(exc)], message=str(exc))

    created = 0
    failed = []

    with transaction.atomic():
        for row in rows:
            try:
                # savepoint هر ردیف: خطای یک ردیف، ردیف‌های قبلی را خراب نمی‌کند
                with transaction.atomic():
                    categories = _get_or_create_categories(row.category_names, user)
                    authors = _get_or_create_named(Author, "name", row.author_names, user, "authors", "نویسنده")
                    publishers = _get_or_create_named(
                        Publisher, "name", [row.publisher_name] if row.publisher_name else [], user, "publisher", "ناشر"
                    )
                    serializer = BookCreateUpdateSerializer(
                        data={
                            **row.payload,
                            "categories": [c.pk for c in categories],
                            "authors": [a.pk for a in authors],
                            "publisher": publishers[0].pk if publishers else None,
                        }
                    )
                    serializer.is_valid(raise_exception=True)
                    serializer.save(created_by=user, updated_by=user)
            except serializers.ValidationError as exc:
                failed.append({
                    "row": row.number,
                    "title": row.payload.get("title", ""),
                    "errors": flatten_errors(exc.detail),
                })
                continue
            created += 1

        if failed and not skip_invalid:
            transaction.set_rollback(True)
            created = 0

    return {"total": len(rows), "created": created, "failed": failed}

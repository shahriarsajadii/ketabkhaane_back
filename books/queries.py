from .models import Book


def book_queryset():
    """کوئری‌ست استاندارد کتاب‌ها (بدون N+1 برای آدرس‌ها، دسته‌ها، نویسنده‌ها و ناشر)"""
    return (
        Book.objects
        .select_related("created_by", "publisher")
        .prefetch_related("copies", "categories", "authors")
    )

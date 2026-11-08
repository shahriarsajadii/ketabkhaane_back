"""
کوئری‌های داشبورد (فقط خواندن). هیچ منطق HTTP اینجا نیست؛ ویوها فقط این توابع را صدا می‌زنند.

نکته: Book یک property به نام `count` دارد، برای همین در annotate ها از اسم `total` استفاده شده.
"""
from collections import defaultdict

from django.db.models import Count, F, Prefetch, Q

from authors.models import Author
from books.addresses import normalize_address
from books.models import Book, BookCopy, BookSeries
from categories.models import Category
from publishers.models import Publisher

DEFAULT_TOP = 10


# -----------------------------------------------------
# فیلتر سراسری (برای کراس‌فیلترینگِ شبیه Power BI)
# -----------------------------------------------------
def _parse_ids(raw):
    if not raw:
        return None
    ids = [int(part) for part in str(raw).split(",") if part.strip().isdigit()]
    return ids or None


def parse_filters(query_params):
    """
    پارامترهای فیلتر مشترکِ همه‌ی اندپوینت‌های داشبورد را از querystring می‌خواند:
    category, author, publisher, series (هرکدام چند شناسه با کاما)،
    year_from, year_to و is_loaned (true/false).
    خروجی دیکشنری فیلترهاست؛ اگر چیزی ست نشده باشد، آن کلید اصلاً در خروجی نیست.
    """
    filters = {}
    for key in ("category", "author", "publisher", "series"):
        ids = _parse_ids(query_params.get(key))
        if ids:
            filters[key] = ids

    for key in ("year_from", "year_to"):
        raw = query_params.get(key)
        if raw not in (None, ""):
            try:
                filters[key] = int(raw)
            except ValueError:
                pass

    raw_loaned = query_params.get("is_loaned")
    if raw_loaned not in (None, ""):
        filters["is_loaned"] = str(raw_loaned).strip().lower() in {"1", "true", "yes"}

    return filters


def filtered_book_ids(filters):
    """
    دیکشنری فیلترها → queryset شناسه‌ی کتاب‌های منطبق، یا None اگر هیچ فیلتری ست نشده
    (یعنی «همه‌ی کتاب‌ها»؛ None نگه داشته می‌شود تا در annotate ها فیلتر اضافه‌ای اعمال نشود).
    """
    if not filters:
        return None

    qs = Book.objects.all()
    if filters.get("category"):
        qs = qs.filter(categories__id__in=filters["category"])
    if filters.get("author"):
        qs = qs.filter(authors__id__in=filters["author"])
    if filters.get("publisher"):
        qs = qs.filter(publisher_id__in=filters["publisher"])
    if filters.get("series"):
        qs = qs.filter(series_id__in=filters["series"])
    if "year_from" in filters:
        qs = qs.filter(publish_year__gte=filters["year_from"])
    if "year_to" in filters:
        qs = qs.filter(publish_year__lte=filters["year_to"])
    if "is_loaned" in filters:
        qs = qs.filter(copies__is_loaned=filters["is_loaned"])

    return qs.values_list("id", flat=True).distinct()


def _books_q(book_ids, field="books__id__in"):
    """Q خالی اگر فیلتری نباشد، وگرنه محدود به book_ids."""
    return Q(**{field: book_ids}) if book_ids is not None else Q()


# -----------------------------------------------------
# helperها
# -----------------------------------------------------
def parse_limit(raw, default=DEFAULT_TOP):
    """
    ?limit=10   → ۱۰ مورد برتر
    ?limit=all  یا ?limit=0 → همه
    خالی / نامعتبر / منفی → default
    خروجی None یعنی «همه».
    """
    if raw is None or str(raw).strip() == "":
        return default
    text = str(raw).strip().lower()
    if text in {"all", "0"}:
        return None
    try:
        number = int(text)
    except ValueError:
        return default
    return number if number > 0 else default


def _top_n(queryset, limit, extra=()):
    """queryset باید values('id', 'name', 'total', ...) داشته و مرتب شده باشد؛ extra = فیلدهای اضافه‌ی خروجی."""
    total_items = queryset.count()
    rows = queryset if limit is None else queryset[:limit]
    items = [
        {"id": r["id"], "name": r["name"], "count": r["total"], **{k: r[k] for k in extra}}
        for r in rows
    ]
    return {
        "limit": limit,
        "total_items": total_items,      # تعداد کل آیتم‌ها (برای max اسلایدر «چندتای برتر»)
        "shown_items": len(items),
        "items": items,
    }


# -----------------------------------------------------
# کارت‌های بالای داشبورد
# -----------------------------------------------------
def summary(book_ids=None):
    books_qs = Book.objects.all() if book_ids is None else Book.objects.filter(id__in=book_ids)
    copies_qs = BookCopy.objects.all() if book_ids is None else BookCopy.objects.filter(book_id__in=book_ids)

    copies = copies_qs.count()
    loaned = copies_qs.filter(is_loaned=True).count()
    return {
        "books": books_qs.count(),
        "copies": copies,
        "authors": Author.objects.filter(_books_q(book_ids)).distinct().count(),
        "categories": Category.objects.filter(_books_q(book_ids)).distinct().count(),
        "series": BookSeries.objects.filter(_books_q(book_ids)).distinct().count(),
        "publishers": Publisher.objects.filter(_books_q(book_ids)).distinct().count(),
        "loaned_copies": loaned,
        "available_copies": copies - loaned,
    }


# -----------------------------------------------------
# نمودارهای «N مورد برتر»
# -----------------------------------------------------
def books_by_author(limit, book_ids=None):
    qs = (
        Author.objects
        .annotate(total=Count("books", filter=_books_q(book_ids), distinct=True))
        .filter(total__gt=0)
        .order_by("-total", "name")
        .values("id", "name", "total")
    )
    return _top_n(qs, limit)


def books_by_category(limit, book_ids=None):
    qs = (
        Category.objects
        .annotate(total=Count("books", filter=_books_q(book_ids), distinct=True), name=F("title"))
        .filter(total__gt=0)
        .order_by("-total", "title")
        .values("id", "name", "total")
    )
    return _top_n(qs, limit)


def books_by_publisher(limit, book_ids=None):
    qs = (
        Publisher.objects
        .annotate(total=Count("books", filter=_books_q(book_ids), distinct=True))
        .filter(total__gt=0)
        .order_by("-total", "name")
        .values("id", "name", "total")
    )
    data = _top_n(qs, limit)
    without_publisher = Book.objects.filter(publisher__isnull=True)
    if book_ids is not None:
        without_publisher = without_publisher.filter(id__in=book_ids)
    data["books_without_publisher"] = without_publisher.count()
    return data


def copies_by_book(limit, book_ids=None):
    base = Book.objects.all() if book_ids is None else Book.objects.filter(id__in=book_ids)
    qs = (
        base
        .annotate(total=Count("copies", distinct=True), name=F("title"))
        .order_by("-total", "title", "id")
        .values("id", "name", "total", "volume_number")
    )
    # volume_number برای تفکیک جلدهای هم‌نام (مثلا دهخدا ۱، ۲، ...)
    return _top_n(qs, limit, extra=("volume_number",))


# -----------------------------------------------------
# سال انتشار
# -----------------------------------------------------
def books_by_year(bucket=1, book_ids=None):
    """
    bucket=1  → تعداد کتاب در هر سال
    bucket=10 → گروه‌بندی ده‌ساله (مثلا 1390–1399)
    کتاب‌های بدون سال در `unknown` می‌آیند.
    """
    bucket = max(int(bucket or 1), 1)
    base = Book.objects.all() if book_ids is None else Book.objects.filter(id__in=book_ids)
    rows = (
        base
        .filter(publish_year__isnull=False)
        .values("publish_year")
        .annotate(total=Count("id"))
        .order_by("publish_year")
    )

    grouped = defaultdict(int)
    for row in rows:
        start = (row["publish_year"] // bucket) * bucket
        grouped[start] += row["total"]

    items = []
    for start in sorted(grouped):
        label = str(start) if bucket == 1 else f"{start}–{start + bucket - 1}"
        items.append({"from": start, "to": start + bucket - 1, "label": label, "count": grouped[start]})

    return {
        "bucket": bucket,
        "items": items,
        "unknown": base.filter(publish_year__isnull=True).count(),
    }


# -----------------------------------------------------
# پراکندگی نسخه‌ها در قفسه‌ها (آدرس = «قفسه-ردیف» مثل 01-05)
# -----------------------------------------------------
def copies_by_shelf(book_ids=None):
    copies_qs = BookCopy.objects.all() if book_ids is None else BookCopy.objects.filter(book_id__in=book_ids)
    rows = copies_qs.values("address").annotate(total=Count("id"))

    cells = defaultdict(int)       # (shelf, row) -> count
    shelf_totals = defaultdict(int)
    invalid = 0

    for row in rows:
        try:
            parsed = normalize_address(row["address"], shelf_max=99, row_max=99)
        except ValueError:
            invalid += row["total"]
            continue
        shelf, shelf_row = (int(part) for part in parsed.split("-"))
        cells[(shelf, shelf_row)] += row["total"]
        shelf_totals[shelf] += row["total"]

    shelves = [
        {
            "shelf": shelf,
            "label": f"{shelf:02d}",
            "count": shelf_totals[shelf],
            "rows_used": sum(1 for (s, _r) in cells if s == shelf),
        }
        for shelf in sorted(shelf_totals)
    ]
    heatmap_cells = [
        {"shelf": shelf, "row": r, "count": count}
        for (shelf, r), count in sorted(cells.items())
    ]

    return {
        # نمودار میله‌ای: تعداد نسخه در هر قفسه
        "shelves": shelves,
        # Heatmap: فقط سلول‌های غیرخالی؛ بقیه‌ی خانه‌های شبکه را فرانت صفر در نظر بگیرد
        "heatmap": {
            "max_shelf": max(shelf_totals) if shelf_totals else 0,
            "max_row": max((r for (_s, r) in cells), default=0),
            "max_count": max(cells.values(), default=0),
            "cells": heatmap_cells,
        },
        "total_copies": sum(shelf_totals.values()),
        "invalid_address_copies": invalid,   # نسخه‌هایی که آدرسشان به شکل «قفسه-ردیف» نیست
    }


# -----------------------------------------------------
# مجموعه‌ها و کتاب‌های هر مجموعه
# -----------------------------------------------------
def series_overview(limit=None, search=None, book_ids=None):
    volumes_qs = Book.objects.all() if book_ids is None else Book.objects.filter(id__in=book_ids)
    books_prefetch = Prefetch(
        "books",
        queryset=(
            volumes_qs
            .annotate(copies_total=Count("copies", distinct=True))
            .order_by("volume_number", "title", "id")
        ),
        to_attr="series_books",
    )

    qs = (
        BookSeries.objects
        .annotate(books_total=Count("books", filter=_books_q(book_ids), distinct=True))
        .order_by("-books_total", "title")
        .prefetch_related(books_prefetch)
    )
    if book_ids is not None:
        qs = qs.filter(books_total__gt=0)
    if search:
        qs = qs.filter(title__icontains=search)

    total_items = qs.count()
    rows = qs if limit is None else qs[:limit]

    items = []
    for series in rows:
        books = [
            {
                "id": book.id,
                "title": book.title,
                "volume_number": book.volume_number,
                "copies_count": book.copies_total,
            }
            for book in series.series_books
        ]
        items.append({
            "id": series.id,
            "title": series.title,
            "books_count": series.books_total,
            "copies_count": sum(b["copies_count"] for b in books),
            "books": books,
        })

    return {"limit": limit, "total_items": total_items, "items": items}
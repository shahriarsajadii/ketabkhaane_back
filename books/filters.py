import django_filters
from django.db.models import Q

from .models import Book


def _parse_ids(value):
    """«1,4» → [1, 4]"""
    return [int(part) for part in value.split(",") if part.strip().isdigit()]


class BookFilter(django_filters.FilterSet):
    # جستجوی کلی: نام، نویسنده‌ها، مترجم، ناشر، شابک، یادداشت و آدرس قفسه
    search = django_filters.CharFilter(method="filter_search")

    title = django_filters.CharFilter(field_name="title", lookup_expr="icontains")
    translator = django_filters.CharFilter(field_name="translator", lookup_expr="icontains")
    publish_year = django_filters.NumberFilter(field_name="publish_year")

    # بر اساس شناسه: یک یا چند نویسنده/ناشر (با کاما)، مثلا ?author=3,7  → کتاب‌هایی که هرکدام را داشته باشند
    author = django_filters.CharFilter(method="filter_author")
    publisher = django_filters.CharFilter(method="filter_publisher")
    # بر اساس نام (جستجوی بخشی)
    author_name = django_filters.CharFilter(field_name="authors__name", lookup_expr="icontains", distinct=True)
    publisher_name = django_filters.CharFilter(field_name="publisher__name", lookup_expr="icontains")

    # آدرس قفسه، مثلا ?address=01-05  یا فقط قفسه: ?address=01-
    address = django_filters.CharFilter(method="filter_address")
    # یک یا چند دسته (با کاما)، مثلا ?category=1,4  → کتاب‌هایی که در هرکدام باشند
    category = django_filters.CharFilter(method="filter_category")

    ordering = django_filters.OrderingFilter(
        fields=(
            ("title", "title"),
            ("publisher__name", "publisher"),
            ("publish_year", "publish_year"),
            ("created_at", "created_at"),
            ("updated_at", "updated_at"),
        )
    )

    class Meta:
        model = Book
        fields = [
            "search", "title", "translator", "publish_year",
            "author", "publisher", "author_name", "publisher_name",
            "address", "category",
        ]

    def filter_search(self, queryset, name, value):
        value = value.strip()
        if not value:
            return queryset
        return queryset.filter(
            Q(title__icontains=value)
            | Q(authors__name__icontains=value)
            | Q(translator__icontains=value)
            | Q(publisher__name__icontains=value)
            | Q(isbn__icontains=value)
            | Q(note__icontains=value)
            | Q(copies__address__icontains=value)
        ).distinct()

    def filter_address(self, queryset, name, value):
        value = value.strip()
        if not value:
            return queryset
        return queryset.filter(copies__address__icontains=value).distinct()

    def filter_author(self, queryset, name, value):
        ids = _parse_ids(value)
        if not ids:
            return queryset
        return queryset.filter(authors__id__in=ids).distinct()

    def filter_publisher(self, queryset, name, value):
        ids = _parse_ids(value)
        if not ids:
            return queryset
        return queryset.filter(publisher_id__in=ids)

    def filter_category(self, queryset, name, value):
        ids = _parse_ids(value)
        if not ids:
            return queryset
        return queryset.filter(categories__id__in=ids).distinct()

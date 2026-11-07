import django_filters
from django.db.models import Q

from .models import Author


class AuthorFilter(django_filters.FilterSet):
    # جستجوی کلی (برای combobox فرانت): نام یا توضیحات
    search = django_filters.CharFilter(method="filter_search")
    name = django_filters.CharFilter(field_name="name", lookup_expr="icontains")
    description = django_filters.CharFilter(field_name="description", lookup_expr="icontains")

    ordering = django_filters.OrderingFilter(
        fields=(
            ("name", "name"),
            ("created_at", "created_at"),
            ("updated_at", "updated_at"),
            ("books_count", "books_count"),
        )
    )

    class Meta:
        model = Author
        fields = ["search", "name", "description"]

    def filter_search(self, queryset, name, value):
        value = value.strip()
        if not value:
            return queryset
        return queryset.filter(Q(name__icontains=value) | Q(description__icontains=value))

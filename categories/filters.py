import django_filters

from .models import Category


class CategoryFilter(django_filters.FilterSet):
    title = django_filters.CharFilter(field_name="title", lookup_expr="icontains")

    ordering = django_filters.OrderingFilter(
        fields=(
            ("title", "title"),
            ("created_at", "created_at"),
            ("books_count", "books_count"),
        )
    )

    class Meta:
        model = Category
        fields = ["title"]

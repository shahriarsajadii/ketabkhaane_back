import django_filters

from .models import Publisher


class PublisherFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(field_name="name", lookup_expr="icontains")
    name = django_filters.CharFilter(field_name="name", lookup_expr="icontains")

    ordering = django_filters.OrderingFilter(
        fields=(
            ("name", "name"),
            ("created_at", "created_at"),
            ("updated_at", "updated_at"),
            ("books_count", "books_count"),
        )
    )

    class Meta:
        model = Publisher
        fields = ["search", "name"]

import django_filters
from django.db.models import Q

from .models import User


class UserFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method="search_user")
    is_active = django_filters.BooleanFilter(field_name="is_active")
    is_staff = django_filters.BooleanFilter(field_name="is_staff")

    ordering = django_filters.OrderingFilter(
        fields=(
            ("name", "name"),
            ("username", "username"),
            ("created_at", "created_at"),
        )
    )

    class Meta:
        model = User
        fields = ["search", "is_active", "is_staff"]

    def search_user(self, queryset, name, value):
        return queryset.filter(Q(name__icontains=value) | Q(username__icontains=value))

from django.db.models import Count
from rest_framework.views import APIView

from core.images import ImageUploadView
from core.permissions import MethodPermission
from core.responses import ResponseHelper
from core.views import BulkDeleteMixin, CreateMixin, DeleteMixin, ListMixin, RetrieveMixin, UpdateMixin

from .consts import (
    PublisherImagePermissions,
    PublisherListCreatePermissions,
    PublisherRetrieveUpdateDeletePermissions,
)
from .filters import PublisherFilter
from .models import Publisher
from .serializers import PublisherBulkDeleteSerializer, PublisherCreateUpdateSerializer, PublisherSerializer

publisher_rh = ResponseHelper("ناشر", "ناشران")


def publisher_queryset():
    return Publisher.objects.annotate(books_count=Count("books", distinct=True))


class PublisherListCreate(ListMixin, CreateMixin, BulkDeleteMixin, APIView):
    """
    GET /api/publishers/?search=...&page=1&page_size=25&ordering=name
    (برای combobox فرانت: ?search=...&page_size=20)
    """
    response_helper = publisher_rh
    permission_classes = [MethodPermission]
    permission_by_method = PublisherListCreatePermissions

    filterset_class = PublisherFilter
    list_serializer_class = PublisherSerializer
    create_serializer_class = PublisherCreateUpdateSerializer
    bulk_delete_serializer_class = PublisherBulkDeleteSerializer

    def get_queryset(self):
        return publisher_queryset().order_by("name", "id")

    def _create_save_kwargs(self, request):
        return {"created_by": request.user, "updated_by": request.user}


class PublisherRetrieveUpdateDelete(RetrieveMixin, UpdateMixin, DeleteMixin, APIView):
    """حذف ناشر، کتاب‌هایش را حذف نمی‌کند؛ فقط ناشرِ آن کتاب‌ها خالی می‌شود (SET_NULL)."""
    response_helper = publisher_rh
    permission_classes = [MethodPermission]
    permission_by_method = PublisherRetrieveUpdateDeletePermissions

    retrieve_serializer_class = PublisherSerializer
    update_serializer_class = PublisherCreateUpdateSerializer

    def get_queryset(self):
        return publisher_queryset()

    def get_update_save_kwargs(self, request):
        return {"updated_by": request.user}


class PublisherImage(ImageUploadView):
    """
    POST   /api/publishers/<id>/image/   (multipart: image=<file>)
    DELETE /api/publishers/<id>/image/
    """
    model = Publisher
    response_helper = publisher_rh
    permission_classes = [MethodPermission]
    permission_by_method = PublisherImagePermissions

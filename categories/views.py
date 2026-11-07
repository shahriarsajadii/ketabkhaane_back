from django.db.models import Count
from rest_framework.views import APIView

from core.permissions import MethodPermission
from core.responses import ResponseHelper
from core.views import BulkDeleteMixin, CreateMixin, DeleteMixin, ListMixin, RetrieveMixin, UpdateMixin

from .consts import CategoryListCreatePermissions, CategoryRetrieveUpdateDeletePermissions
from .filters import CategoryFilter
from .models import Category
from .serializers import CategoryBulkDeleteSerializer, CategoryCreateUpdateSerializer, CategorySerializer

cat_rh = ResponseHelper("دسته‌بندی", "دسته‌بندی‌ها")


def category_queryset():
    return Category.objects.annotate(books_count=Count("books", distinct=True))


class CategoryListCreate(ListMixin, CreateMixin, BulkDeleteMixin, APIView):
    response_helper = cat_rh
    permission_classes = [MethodPermission]
    permission_by_method = CategoryListCreatePermissions

    queryset = category_queryset()
    filterset_class = CategoryFilter
    pagination_enabled = False  # برای dropdown فرانت: همه‌ی دسته‌ها یکجا

    list_serializer_class = CategorySerializer
    create_serializer_class = CategoryCreateUpdateSerializer
    bulk_delete_serializer_class = CategoryBulkDeleteSerializer

    def _create_save_kwargs(self, request):
        return {"created_by": request.user, "updated_by": request.user}


class CategoryRetrieveUpdateDelete(RetrieveMixin, UpdateMixin, DeleteMixin, APIView):
    response_helper = cat_rh
    permission_classes = [MethodPermission]
    permission_by_method = CategoryRetrieveUpdateDeletePermissions

    queryset = category_queryset()
    retrieve_serializer_class = CategorySerializer
    update_serializer_class = CategoryCreateUpdateSerializer

    def get_update_save_kwargs(self, request):
        return {"updated_by": request.user}

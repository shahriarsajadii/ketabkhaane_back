from django.db.models import Count
from rest_framework.views import APIView

from core.images import ImageUploadView
from core.permissions import MethodPermission
from core.responses import ResponseHelper
from core.views import BulkDeleteMixin, CreateMixin, DeleteMixin, ListMixin, RetrieveMixin, UpdateMixin

from .consts import AuthorImagePermissions, AuthorListCreatePermissions, AuthorRetrieveUpdateDeletePermissions
from .filters import AuthorFilter
from .models import Author
from .serializers import AuthorBulkDeleteSerializer, AuthorCreateUpdateSerializer, AuthorSerializer

author_rh = ResponseHelper("نویسنده", "نویسنده‌ها")


def author_queryset():
    return Author.objects.annotate(books_count=Count("books", distinct=True))


class AuthorListCreate(ListMixin, CreateMixin, BulkDeleteMixin, APIView):
    """
    GET /api/authors/?search=...&page=1&page_size=25&ordering=name
    (برای combobox فرانت: ?search=...&page_size=20)
    """
    response_helper = author_rh
    permission_classes = [MethodPermission]
    permission_by_method = AuthorListCreatePermissions

    filterset_class = AuthorFilter
    list_serializer_class = AuthorSerializer
    create_serializer_class = AuthorCreateUpdateSerializer
    bulk_delete_serializer_class = AuthorBulkDeleteSerializer

    def get_queryset(self):
        return author_queryset().order_by("name", "id")

    def _create_save_kwargs(self, request):
        return {"created_by": request.user, "updated_by": request.user}


class AuthorRetrieveUpdateDelete(RetrieveMixin, UpdateMixin, DeleteMixin, APIView):
    response_helper = author_rh
    permission_classes = [MethodPermission]
    permission_by_method = AuthorRetrieveUpdateDeletePermissions

    retrieve_serializer_class = AuthorSerializer
    update_serializer_class = AuthorCreateUpdateSerializer

    def get_queryset(self):
        return author_queryset()

    def get_update_save_kwargs(self, request):
        return {"updated_by": request.user}

    def validate_delete(self, request, item):
        # نویسنده برای کتاب اجباری است؛ پس نویسنده‌ی دارای کتاب حذف نمی‌شود
        count = item.books.count()
        if count:
            return author_rh.failed_response(
                message=f"این نویسنده {count} کتاب دارد و حذف نمی‌شود. ابتدا کتاب‌هایش را ویرایش یا حذف کنید.",
                errors={"author": ["نویسنده دارای کتاب است."]},
            )
        return None


class AuthorImage(ImageUploadView):
    """
    POST   /api/authors/<id>/image/   (multipart: image=<file>)
    DELETE /api/authors/<id>/image/
    """
    model = Author
    response_helper = author_rh
    permission_classes = [MethodPermission]
    permission_by_method = AuthorImagePermissions

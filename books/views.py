from django.db.models import Max
from django.http import HttpResponse
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.views import APIView

from core.permissions import MethodPermission
from core.responses import ResponseHelper
from core.utils import get_object
from core.views import BulkDeleteMixin, CreateMixin, DeleteMixin, ListMixin, RetrieveMixin, UpdateMixin
from django.db.models import Count

from .consts import (
    BookExportPermissions,
    BookImagePermissions,
    BookImportPermissions,
    BookImportTemplatePermissions,
    BookListCreatePermissions,
    BookRetrieveUpdateDeletePermissions,
    BookSeriesListCreatePermissions,
    BookSeriesRetrieveUpdateDeletePermissions,
    BookStatsPermissions,
)
from .excel import XLSX_CONTENT_TYPE, build_export, build_template
from .filters import BookFilter
from .models import Book, BookCopy, BookSeries
from .queries import book_queryset
from .serializers import (
    BookBulkDeleteSerializer,
    BookCreateUpdateSerializer,
    BookDetailSerializer,
    BookListSerializer,
    BookSeriesBulkDeleteSerializer,
    BookSeriesCreateUpdateSerializer,
    BookSeriesSerializer,
    ExcelUploadSerializer,
    BookImageSerializer,
)
from .services import import_books_from_excel

book_rh = ResponseHelper("کتاب", "کتاب‌ها")
series_rh = ResponseHelper("مجموعه", "مجموعه‌ها")


# مجموعه‌ ها
def _series_queryset():
    return BookSeries.objects.annotate(books_count=Count("books", distinct=True))


class BookSeriesListCreate(ListMixin, CreateMixin, BulkDeleteMixin, APIView):
    response_helper = series_rh
    permission_classes = [MethodPermission]
    permission_by_method = BookSeriesListCreatePermissions

    queryset = _series_queryset()
    pagination_enabled = False

    list_serializer_class = BookSeriesSerializer
    create_serializer_class = BookSeriesCreateUpdateSerializer
    bulk_delete_serializer_class = BookSeriesBulkDeleteSerializer

    def _create_save_kwargs(self, request):
        return {"created_by": request.user, "updated_by": request.user}


class BookSeriesRetrieveUpdateDelete(RetrieveMixin, UpdateMixin, DeleteMixin, APIView):
    response_helper = series_rh
    permission_classes = [MethodPermission]
    permission_by_method = BookSeriesRetrieveUpdateDeletePermissions

    queryset = _series_queryset()
    retrieve_serializer_class = BookSeriesSerializer
    update_serializer_class = BookSeriesCreateUpdateSerializer

    def get_update_save_kwargs(self, request):
        return {"updated_by": request.user}


# =====================================================
# CRUD
# =====================================================
class BookListCreate(ListMixin, CreateMixin, BulkDeleteMixin, APIView):
    response_helper = book_rh
    permission_classes = [MethodPermission]
    permission_by_method = BookListCreatePermissions

    filterset_class = BookFilter
    list_serializer_class = BookListSerializer
    create_serializer_class = BookCreateUpdateSerializer
    bulk_delete_serializer_class = BookBulkDeleteSerializer

    def get_queryset(self):
        return book_queryset().order_by("-created_at", "-id")

    def _create_save_kwargs(self, request):
        return {"created_by": request.user, "updated_by": request.user}


class BookRetrieveUpdateDelete(RetrieveMixin, UpdateMixin, DeleteMixin, APIView):
    response_helper = book_rh
    permission_classes = [MethodPermission]
    permission_by_method = BookRetrieveUpdateDeletePermissions

    lookup_fields = ["id"]
    retrieve_serializer_class = BookDetailSerializer
    update_serializer_class = BookCreateUpdateSerializer

    def get_queryset(self):
        return book_queryset()

    def get_update_save_kwargs(self, request):
        return {"updated_by": request.user}



class BookImage(APIView):
    """
    POST   /api/books/<id>/image/
    DELETE /api/books/<id>/image/
    """
    permission_classes = [MethodPermission]
    permission_by_method = BookImagePermissions
    parser_classes = [MultiPartParser, FormParser]

    @staticmethod
    def _image_url(request, book):
        return request.build_absolute_uri(book.image.url) if book.image else None

    def post(self, request, param):
        book = get_object(Book.objects.all(), param)
        if book is None:
            return book_rh.not_found_response()

        serializer = BookImageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        old_name = book.image.name if book.image else None
        book.image = serializer.validated_data["image"]
        book.updated_by = request.user
        book.save()

        # فایل قبلی رو بعد از ذخیره ‌ی موفق پاک می‌ کنیم
        if old_name and old_name != book.image.name:
            book.image.storage.delete(old_name)

        return book_rh.success_update_response(
            message="عکس کتاب ذخیره شد.",
            data={"image": self._image_url(request, book)},
        )

    def delete(self, request, param):
        book = get_object(Book.objects.all(), param)
        if book is None:
            return book_rh.not_found_response()

        if book.image:
            book.image.delete(save=False)
            book.image = None
            book.updated_by = request.user
            book.save()
        return book_rh.success_delete_response(message="عکس کتاب حذف شد.")


# =====================================================
# اکسل
# =====================================================
class BookImport(APIView):
    """
    POST /api/books/import/            (multipart: file=<xlsx>)
    POST /api/books/import/?skip_invalid=true

    پیش‌فرض همه یا هیچ عه (اگه یک ردیف خطا داشت چیزی ثبت نمیشه و لیست خطا ها برمیگرده).
    با skip_invalid=true ردیف‌ های سالم ثبت و ردیف‌ های خراب در data.failed گزارش میشه.
    """
    permission_classes = [MethodPermission]
    permission_by_method = BookImportPermissions
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = ExcelUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        uploaded = serializer.validated_data["file"]

        skip_invalid = request.query_params.get("skip_invalid", "").lower() in {"1", "true", "yes"}
        result = import_books_from_excel(uploaded.read(), request.user, skip_invalid=skip_invalid)

        if result["failed"] and not skip_invalid:
            return book_rh.error(
                message="در فایل خطا وجود دارد؛ هیچ کتابی ثبت نشد. خطاها را اصلاح و دوباره آپلود کنید.",
                errors={"rows": result["failed"]},
                data=result,
            )

        if result["failed"]:
            message = f"{result['created']} کتاب ثبت شد و {len(result['failed'])} ردیف به‌دلیل خطا ثبت نشد."
        else:
            message = f"{result['created']} کتاب با موفقیت ثبت شد."

        return book_rh.success(message=message, data=result, status_code=201)


class BookImportTemplate(APIView):
    """فایل نمونه‌ ی اکسل"""
    permission_classes = [MethodPermission]
    permission_by_method = BookImportTemplatePermissions

    def get(self, request):
        response = HttpResponse(build_template(), content_type=XLSX_CONTENT_TYPE)
        response["Content-Disposition"] = 'attachment; filename="books-template.xlsx"'
        return response


class BookExport(APIView):

    permission_classes = [MethodPermission]
    permission_by_method = BookExportPermissions

    def get(self, request):
        queryset = book_queryset().order_by("title", "id")
        queryset = BookFilter(request.GET, queryset=queryset, request=request).qs

        rows = [
            {
                "title": book.title,
                "author": "، ".join(author.name for author in book.authors.all()),
                "translator": book.translator,
                "count": book.count,
                "addresses": " | ".join(copy.address for copy in book.copies.all()),
                "publisher": book.publisher.name if book.publisher else "",
                "publish_year": book.publish_year,
                "isbn": book.isbn,
                "categories": "، ".join(category.title for category in book.categories.all()),
                "note": book.note,
            }
            for book in queryset
        ]

        response = HttpResponse(build_export(rows), content_type=XLSX_CONTENT_TYPE)
        response["Content-Disposition"] = 'attachment; filename="books.xlsx"'
        return response


class BookStats(APIView):
    permission_classes = [MethodPermission]
    permission_by_method = BookStatsPermissions

    def get(self, request):
        titles = Book.objects.count()
        copies = BookCopy.objects.count()
        years = list(
            Book.objects.exclude(publish_year__isnull=True)
            .order_by("-publish_year")
            .values_list("publish_year", flat=True)
            .distinct()
        )
        last_updated = Book.objects.aggregate(last=Max("updated_at"))["last"]

        return book_rh.success_get_one_response({
            "titles": titles,
            "copies": copies,
            "languages": [],
            "years": years,
            "last_updated": last_updated,
        })
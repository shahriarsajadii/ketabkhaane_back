from urllib.parse import urljoin

from django.db.models import Max
from django.http import HttpResponse
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.views import APIView

from core.permissions import MethodPermission
from core.responses import ResponseHelper
from core.utils import get_object
from core.views import BulkDeleteMixin, CreateMixin, DeleteMixin, ListMixin, RetrieveMixin, UpdateMixin
import requests
from bs4 import BeautifulSoup
from .consts import (
    BookExportPermissions,
    BookImagePermissions,
    BookImportPermissions,
    BookImportTemplatePermissions,
    BookListCreatePermissions,
    BookRetrieveUpdateDeletePermissions,
BookStatsPermissions

)
from .excel import XLSX_CONTENT_TYPE, build_export, build_template
from .filters import BookFilter
from .models import Book, BookCopy
from .queries import book_queryset
from .serializers import (
    BookBulkDeleteSerializer,
    BookCreateUpdateSerializer,
    BookDetailSerializer,
    BookListSerializer,
    ExcelUploadSerializer,
    BookImageSerializer,
)
from .services import import_books_from_excel

book_rh = ResponseHelper("کتاب", "کتاب‌ها")


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


# =====================================================
# عکس کتاب (multipart)
# =====================================================
class BookImage(APIView):
    """
    POST   /api/books/<id>/image/   (multipart: image=<file>)  → آپلود یا جایگزینی
    DELETE /api/books/<id>/image/                              → حذف عکس
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

        # فایل قبلی را بعد از ذخیره‌ی موفق پاک می‌کنیم
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

    پیش‌فرض: همه یا هیچ (اگر یک ردیف خطا داشت چیزی ثبت نمی‌شود و لیست خطاها برمی‌گردد).
    با skip_invalid=true ردیف‌های سالم ثبت و ردیف‌های خراب در data.failed گزارش می‌شوند.
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
    """GET /api/books/import/template/  → فایل نمونه‌ی اکسل"""
    permission_classes = [MethodPermission]
    permission_by_method = BookImportTemplatePermissions

    def get(self, request):
        response = HttpResponse(build_template(), content_type=XLSX_CONTENT_TYPE)
        response["Content-Disposition"] = 'attachment; filename="books-template.xlsx"'
        return response


class BookExport(APIView):
    """
    GET /api/books/export/   → خروجی اکسل همه‌ی کتاب‌ها
    همان فیلترهای لیست کار می‌کنند: ?search=...&category=1,2&address=قفسه ۲&ordering=title
    """
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
    """GET /api/books/stats/  → تعداد عنوان‌ها، تعداد کل نسخه‌ها و فیلترهای کمکی"""
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


class SearchBookByShabak(APIView):
    def post(self, request):

        data = request.data

        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        shabak = data.get('shabak')


        if not shabak:
            return book_rh.failed_response(message="وارد کردن شابک الزامی است.")

        url = "https://opac.nlai.ir/opac-prod/search/bibliographicSimpleSearchProcess.do"

        params = {
            "simpleSearch.value": shabak,
            "bibliographicLimitQueryBuilder.biblioDocType": "",
            "simpleSearch.indexFieldId": "221091",
            "nliHolding": "",
            "command": "I",
            "simpleSearch.tokenized": "true",
            "classType": "0",
            "pageStatus": "0",
            "bibliographicLimitQueryBuilder.useDateRange": "null",
            "bibliographicLimitQueryBuilder.year": "",
            "documentType": "",
            "attributes.locale": "fa",
        }
        try:
            response = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=20
            )

            print(response.text)

            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            books = []
            rows = soup.select("#table tr.gridrownormal3")

            for row in rows:
                title = row.select_one('input[name$=".title"]')
                author = row.select_one('input[name$=".author"]')
                publish_date = row.select_one(
                    'input[name$=".publisherDate"]'
                )
                detail_link = row.select_one('a[href*="briefListSearch.do"]')
                href = detail_link.get("href") if detail_link else None


                book = {
                    "title": title.get("value") if title else None,
                    "author": author.get("value") if author else None,
                    "publish_date": (
                        publish_date.get("value")
                        if publish_date else None
                    ),
                    "detail_url": urljoin(
                        "https://opac.nlai.ir",
                        href
                    ) if href else None
                }

                books.append(book)

            if not books:
                return book_rh.not_found_response()


            return book_rh.success_get_all_response(data=books)
        except requests.RequestException as e:
            return book_rh.failed_response(message="خطا در ارتباط با سامانه کتابخانه ملی", status_code=502)

class GetBookByOpacId(APIView):
    def post(self, request):

        data = request.data

        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        opac_book_id = data.get('opac_book_id')


        if not opac_book_id:
            return book_rh.failed_response(message="وارد کردن آیدی کتاب کتابخانه ملی الزامی است.")

        url = "https://opac.nlai.ir/opac-prod/search/briefListSearch.do"

        params = {
            "command" : "FULL_VIEW",
            "id":opac_book_id,
            "pageStatus" : 0,
            "sortKeyValue1" : "sortkey_title" ,
            "sortKeyValue2" :"sortkey_author"
        }
        try:
            response = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=20
            )

            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            first_field = soup.find(
                lambda tag : tag.name == "td"
                and "سرشناسه" in tag.text(strip=True)
            )

            if not first_field:
                return book_rh.not_found_response()

            table = first_field.find_parent("table")

            if not table:
                return book_rh.not_found_response()

            field_mapping = {
                "سرشناسه": "main_entry",
                "عنوان و نام پدیدآور": "title_and_author",
                "مشخصات نشر": "publication",
                "مشخصات ظاهری": "physical_description",
                "فروست": "series",
                "شابک": "isbn",
                "موضوع": "subjects",
                "شناسه افزوده": "additional_entry",
                "رده بندی کنگره": "lcc",
                "رده بندی دیویی": "dewey",
                "شماره کتابشناسی ملی": "national_bibliography_number",
                "اطلاعات رکورد کتابشناسی": "bibliographic_record_info",
            }

            book_data = {}

            for row in table.find_all("tr", recursive=False):

                columns = row.find_all("td", recursive=False)

                if len(columns) < 3:
                    continue

                field_name = columns[0].get_text(
                    separator=" ",
                    strip=True
                ).replace("\u200f", "").strip()

                # حذف تمام ردیف‌های یادداشت
                if "یادداشت" in field_name:
                    continue

                field_value = columns[2].get_text(
                    separator=" ",
                    strip=True
                )

                # حذف کاراکترهای نامرئی و کنترلی
                field_value = (
                    field_value
                    .replace("\u200f", "")
                    .replace("\u200e", "")
                    .replace("\u202a", "")
                    .replace("\u202b", "")
                    .replace("\u202c", "")
                    .replace("\u202d", "")
                    .replace("\u202e", "")
                    .strip()
                )

                key = field_mapping.get(field_name)

                if key:
                    book_data[key] = field_value

            if not book_data:
                return book_rh.not_found_response()

            return book_rh.success_get_all_response(data=book_data)




        except requests.RequestException:
            return book_rh.failed_response(
                message="خطا در ارتباط با سامانه کتابخانه ملی",
                status_code=502
            )



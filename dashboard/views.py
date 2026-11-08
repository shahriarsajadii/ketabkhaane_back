from rest_framework.views import APIView

from core.permissions import MethodPermission
from core.responses import ResponseHelper

from . import selectors
from .consts import DashboardPermissions

dashboard_rh = ResponseHelper("داشبورد")


class DashboardBaseView(APIView):
    """
    هر ویو فقط build(request, book_ids) را پیاده می‌کند و dict خروجی را برمی‌گرداند.
    book_ids نتیجه‌ی اعمال فیلترهای سراسری (category/author/publisher/series/year_from/year_to/is_loaned)
    روی مدل Book است؛ None یعنی هیچ فیلتری ست نشده (= همه‌ی کتاب‌ها). این فیلترها روی همه‌ی
    کارت‌ها و نمودارهای داشبورد یکسان اعمال می‌شوند تا کراس‌فیلترینگِ شبیه Power BI ممکن باشد.
    """
    permission_classes = [MethodPermission]
    permission_by_method = DashboardPermissions

    def build(self, request, book_ids):
        raise NotImplementedError

    def get(self, request):
        filters = selectors.parse_filters(request.query_params)
        book_ids = selectors.filtered_book_ids(filters)
        data = self.build(request, book_ids)
        data["applied_filters"] = bool(filters)
        return dashboard_rh.success_get_one_response(data)


class DashboardSummary(DashboardBaseView):
    """GET /api/dashboard/summary/ → کارت‌های بالای صفحه"""

    def build(self, request, book_ids):
        return selectors.summary(book_ids)


class BooksByAuthor(DashboardBaseView):
    """GET /api/dashboard/books-by-author/?limit=10  (limit=all → همه)"""

    def build(self, request, book_ids):
        return selectors.books_by_author(selectors.parse_limit(request.query_params.get("limit")), book_ids)


class BooksByCategory(DashboardBaseView):
    """GET /api/dashboard/books-by-category/?limit=10"""

    def build(self, request, book_ids):
        return selectors.books_by_category(selectors.parse_limit(request.query_params.get("limit")), book_ids)


class CopiesByBook(DashboardBaseView):
    """GET /api/dashboard/copies-by-book/?limit=10"""

    def build(self, request, book_ids):
        return selectors.copies_by_book(selectors.parse_limit(request.query_params.get("limit")), book_ids)


class BooksByPublisher(DashboardBaseView):
    """GET /api/dashboard/books-by-publisher/?limit=10"""

    def build(self, request, book_ids):
        return selectors.books_by_publisher(selectors.parse_limit(request.query_params.get("limit")), book_ids)


class CopiesByShelf(DashboardBaseView):
    """GET /api/dashboard/copies-by-shelf/ → تعداد نسخه در هر قفسه + داده‌ی Heatmap قفسه×ردیف"""

    def build(self, request, book_ids):
        return selectors.copies_by_shelf(book_ids)


class BooksByYear(DashboardBaseView):
    """GET /api/dashboard/books-by-year/?bucket=1  (bucket=10 → ده‌ساله)"""

    def build(self, request, book_ids):
        try:
            bucket = int(request.query_params.get("bucket", 1))
        except (TypeError, ValueError):
            bucket = 1
        return selectors.books_by_year(bucket, book_ids)


class SeriesOverview(DashboardBaseView):
    """GET /api/dashboard/series/?search=دهخدا&limit=all → مجموعه‌ها + کتاب‌های هر مجموعه"""

    def build(self, request, book_ids):
        limit = selectors.parse_limit(request.query_params.get("limit"), default=None)
        search = (request.query_params.get("search") or "").strip()
        return selectors.series_overview(limit=limit, search=search, book_ids=book_ids)
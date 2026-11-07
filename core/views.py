"""
Mixin های پایه برای APIView ها (همان الگوی پروژه‌ی نمونه).

یک ویو معمولا این‌طور ساخته می‌شود:

    class XListCreate(ListMixin, CreateMixin, APIView):
        permission_classes = [MethodPermission]
        permission_by_method = XListCreatePermissions
        queryset = X.objects.all()
        filterset_class = XFilter
        list_serializer_class = XSerializer
        create_serializer_class = XCreateSerializer
"""
from core.pagination import StandardResultsSetPagination
from core.responses import ResponseHelper
from core.utils import get_object


class ResponseMixin:
    # در هر ویو با ResponseHelper("کتاب", "کتاب‌ها") جایگزین کن تا پیام‌ها دقیق‌تر شوند
    response_helper = ResponseHelper("")


class QuerysetMixin:
    queryset = None

    def get_queryset(self):
        if self.queryset is None:
            raise NotImplementedError("خطای سیستمی: queryset پیکربندی نشده است.")
        return self.queryset.all()


class FilterMixin:
    filterset_class = None

    def filter_queryset(self, queryset):
        if self.filterset_class is None:
            return queryset
        filterset = self.filterset_class(
            self.request.GET, queryset=queryset, request=self.request,
        )
        return filterset.qs


class PaginationMixin:
    pagination_enabled = True
    pagination_class = StandardResultsSetPagination
    page_size = None

    def paginate_queryset(self, queryset):
        if not self.pagination_enabled:
            return None, queryset
        paginator = self.pagination_class()
        if self.page_size is not None:
            paginator.page_size = self.page_size
        page = paginator.paginate_queryset(queryset, self.request, view=self)
        return paginator, page


class SerializerMixin:
    list_serializer_class = None
    create_serializer_class = None
    retrieve_serializer_class = None
    update_serializer_class = None
    bulk_delete_serializer_class = None

    def get_serializer_context(self):
        return {"request": self.request}

    def _build_serializer(self, cls, name, *args, **kwargs):
        if cls is None:
            raise NotImplementedError(f"خطای سیستمی: {name} پیکربندی نشده است.")
        return cls(*args, context=self.get_serializer_context(), **kwargs)

    def _list_serializer(self, *args, **kwargs):
        return self._build_serializer(self.list_serializer_class, "list_serializer_class", *args, **kwargs)

    def _create_serializer(self, *args, **kwargs):
        return self._build_serializer(self.create_serializer_class, "create_serializer_class", *args, **kwargs)

    def _retrieve_serializer(self, *args, **kwargs):
        return self._build_serializer(self.retrieve_serializer_class, "retrieve_serializer_class", *args, **kwargs)

    def _update_serializer(self, *args, **kwargs):
        return self._build_serializer(self.update_serializer_class, "update_serializer_class", *args, **kwargs)


class ObjectLookupMixin(ResponseMixin, QuerysetMixin):
    lookup_fields = ["id"]

    def get_object(self, param):
        return get_object(self.get_queryset(), param, self.lookup_fields)


class ListMixin(ResponseMixin, QuerysetMixin, FilterMixin, PaginationMixin, SerializerMixin):
    def get(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        queryset = self.filter_queryset(queryset)
        paginator, data = self.paginate_queryset(queryset)

        serializer = self._list_serializer(data, many=True)
        pagination = paginator.pageResponse() if paginator is not None else None

        return self.response_helper.success_get_all_response(
            data=serializer.data, pagination=pagination,
        )


class CreateMixin(ResponseMixin, SerializerMixin):
    def _create_save_kwargs(self, request):
        return {}

    def post(self, request, *args, **kwargs):
        serializer = self._create_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(**self._create_save_kwargs(request))
        return self.response_helper.success_create_response(data=serializer.data)


class BulkDeleteMixin(ResponseMixin, QuerysetMixin, SerializerMixin):
    def _bulk_delete_queryset(self, items):
        model = self.get_queryset().model
        return model._default_manager.filter(pk__in=[item.pk for item in items])

    def delete(self, request, *args, **kwargs):
        if self.bulk_delete_serializer_class is None:
            raise NotImplementedError("خطای سیستمی: bulk_delete_serializer_class پیکربندی نشده است.")

        serializer = self.bulk_delete_serializer_class(
            data=request.data, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)

        self._bulk_delete_queryset(serializer.validated_data["items"]).delete()
        return self.response_helper.success_delete_response()


class RetrieveMixin(ObjectLookupMixin, SerializerMixin):
    def validate_retrieve(self, request, item):
        """اگر Response برگرداند یعنی دسترسی بلاک شده."""
        return None

    def get_retrieve_data(self, request, item):
        return self._retrieve_serializer(item).data

    def get(self, request, param, *args, **kwargs):
        item = self.get_object(param)
        if not item:
            return self.response_helper.not_found_response()
        self.check_object_permissions(request, item)

        blocked = self.validate_retrieve(request, item)
        if blocked:
            return blocked

        return self.response_helper.success_get_one_response(self.get_retrieve_data(request, item))


class UpdateMixin(ObjectLookupMixin, SerializerMixin):
    def get_update_save_kwargs(self, request):
        return {}

    def patch(self, request, param, *args, **kwargs):
        item = self.get_object(param)
        if not item:
            return self.response_helper.not_found_response()
        self.check_object_permissions(request, item)

        serializer = self._update_serializer(instance=item, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(**self.get_update_save_kwargs(request))
        return self.response_helper.success_update_response(data=serializer.data)


class DeleteMixin(ObjectLookupMixin):
    def validate_delete(self, request, item):
        """اگر Response برگرداند یا APIError بدهد یعنی حذف بلاک شده."""
        return None

    def delete(self, request, param, *args, **kwargs):
        item = self.get_object(param)
        if not item:
            return self.response_helper.not_found_response()
        self.check_object_permissions(request, item)

        blocked = self.validate_delete(request, item)
        if blocked:
            return blocked

        item.delete()
        return self.response_helper.success_delete_response()

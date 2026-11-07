from rest_framework.pagination import PageNumberPagination


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 1000

    def pageResponse(self):
        return {
            "items_per_pages": len(self.page.object_list),
            "total_items": self.page.paginator.count,
            "total_pages": self.page.paginator.num_pages,
            "current_page": self.page.number,
            "has_next": self.page.has_next(),
            "has_previous": self.page.has_previous(),
        }

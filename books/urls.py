from django.urls import path

from .opac_views import GetBookByOpacId, SearchBookOpac
from .views import (
    BookExport,
    BookImage,
    BookImport,
    BookImportTemplate,
    BookListCreate,
    BookRetrieveUpdateDelete,
    BookSeriesListCreate,
    BookSeriesRetrieveUpdateDelete,
    BookStats,
)

urlpatterns = [

    path("", BookListCreate.as_view(), name="books.list-create"),
    path("stats/", BookStats.as_view(), name="books.stats"),
    path("detail/<int:param>/", BookRetrieveUpdateDelete.as_view(), name="books.retrieve-update-delete"),
    path("<int:param>/image/", BookImage.as_view(), name="books.image"),

    path("series/", BookSeriesListCreate.as_view(), name="books.series.list-create"),
    path("series/detail/<int:param>/", BookSeriesRetrieveUpdateDelete.as_view(), name="books.series.retrieve-update-delete"),

    # Excel
    path("import/", BookImport.as_view(), name="books.import"),
    path("import/template/", BookImportTemplate.as_view(), name="books.import.template"),
    path("export/", BookExport.as_view(), name="books.export"),
    path("search_by_shabak/", SearchBookOpac.as_view(), name="books.search_by_shabak"),
    path("get_by_opac_id/", GetBookByOpacId.as_view(), name="books.get_by_opac_id"),
]
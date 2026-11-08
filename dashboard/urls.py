from django.urls import path

from .views import (
    BooksByAuthor,
    BooksByCategory,
    BooksByPublisher,
    BooksByYear,
    CopiesByBook,
    CopiesByShelf,
    DashboardSummary,
    SeriesOverview,
)

urlpatterns = [
    path("summary/", DashboardSummary.as_view(), name="dashboard.summary"),
    path("books-by-author/", BooksByAuthor.as_view(), name="dashboard.books-by-author"),
    path("books-by-category/", BooksByCategory.as_view(), name="dashboard.books-by-category"),
    path("copies-by-book/", CopiesByBook.as_view(), name="dashboard.copies-by-book"),
    path("copies-by-shelf/", CopiesByShelf.as_view(), name="dashboard.copies-by-shelf"),
    path("books-by-year/", BooksByYear.as_view(), name="dashboard.books-by-year"),
    path("books-by-publisher/", BooksByPublisher.as_view(), name="dashboard.books-by-publisher"),
    path("series/", SeriesOverview.as_view(), name="dashboard.series"),
]

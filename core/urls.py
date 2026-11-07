from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/users/", include("users.urls")),
    path("api/categories/", include("categories.urls")),
    path("api/publishers/", include("publishers.urls")),
    path("api/authors/", include("authors.urls")),
    path("api/books/", include("books.urls")),

]

# در محیط واقعی فایل‌های media را nginx سرو می‌کند
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

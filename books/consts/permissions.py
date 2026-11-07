from rest_framework.permissions import IsAuthenticated

# همه‌ی کاربران واردشده‌ی کتابخانه به کتاب‌ها دسترسی کامل دارند.
# اگر بخواهی مثلا فقط مدیر بتواند حذف کند، همین‌جا برای "DELETE" کلاس IsLibraryManager را اضافه کن.

BookListCreatePermissions = {
    "GET": [IsAuthenticated],
    "POST": [IsAuthenticated],
    "DELETE": [IsAuthenticated],  # حذف گروهی
}

BookRetrieveUpdateDeletePermissions = {
    "GET": [IsAuthenticated],
    "PATCH": [IsAuthenticated],
    "DELETE": [IsAuthenticated],
}

BookImagePermissions = {
    "POST": [IsAuthenticated],
    "DELETE": [IsAuthenticated],
}

BookImportPermissions = {
    "POST": [IsAuthenticated],
}

BookImportTemplatePermissions = {
    "GET": [IsAuthenticated],
}

BookExportPermissions = {
    "GET": [IsAuthenticated],
}

BookStatsPermissions = {
    "GET": [IsAuthenticated],
}

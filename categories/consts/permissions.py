from rest_framework.permissions import IsAuthenticated

# همه‌ی کاربران واردشده‌ی کتابخانه می‌توانند دسته‌بندی‌ها را مدیریت کنند.
CategoryListCreatePermissions = {
    "GET": [IsAuthenticated],
    "POST": [IsAuthenticated],
    "DELETE": [IsAuthenticated],  # حذف گروهی
}

CategoryRetrieveUpdateDeletePermissions = {
    "GET": [IsAuthenticated],
    "PATCH": [IsAuthenticated],
    "DELETE": [IsAuthenticated],
}

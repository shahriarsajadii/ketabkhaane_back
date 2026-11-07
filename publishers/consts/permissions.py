from rest_framework.permissions import IsAuthenticated

# همه‌ی کاربران واردشده‌ی کتابخانه می‌توانند ناشرها را مدیریت کنند.
PublisherListCreatePermissions = {
    "GET": [IsAuthenticated],
    "POST": [IsAuthenticated],
    "DELETE": [IsAuthenticated],  # حذف گروهی
}

PublisherRetrieveUpdateDeletePermissions = {
    "GET": [IsAuthenticated],
    "PATCH": [IsAuthenticated],
    "DELETE": [IsAuthenticated],
}

PublisherImagePermissions = {
    "POST": [IsAuthenticated],
    "DELETE": [IsAuthenticated],
}

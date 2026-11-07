from rest_framework.permissions import IsAuthenticated

# همه‌ی کاربران واردشده‌ی کتابخانه می‌توانند نویسنده‌ها را مدیریت کنند.
AuthorListCreatePermissions = {
    "GET": [IsAuthenticated],
    "POST": [IsAuthenticated],
    "DELETE": [IsAuthenticated],  # حذف گروهی
}

AuthorRetrieveUpdateDeletePermissions = {
    "GET": [IsAuthenticated],
    "PATCH": [IsAuthenticated],
    "DELETE": [IsAuthenticated],
}

AuthorImagePermissions = {
    "POST": [IsAuthenticated],
    "DELETE": [IsAuthenticated],
}

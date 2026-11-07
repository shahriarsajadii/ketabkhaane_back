from rest_framework.permissions import BasePermission, IsAuthenticated


class IsLibraryManager(BasePermission):
    """فقط «مدیر» (is_staff یا superuser)"""

    message = "فقط مدیر کتابخانه اجازه‌ی این کار را دارد."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and (user.is_staff or user.is_superuser))


# =======================
# Users (مدیریت کاربران فقط برای مدیر)
# =======================
UserListCreatePermissions = {
    "GET": [IsAuthenticated, IsLibraryManager],
    "POST": [IsAuthenticated, IsLibraryManager],
}

UserRetrieveUpdateDeletePermissions = {
    "GET": [IsAuthenticated, IsLibraryManager],
    "PATCH": [IsAuthenticated, IsLibraryManager],
    "DELETE": [IsAuthenticated, IsLibraryManager],
}

# =======================
# پروفایل خود کاربر (هر کاربر واردشده)
# =======================
MePermissions = {
    "GET": [IsAuthenticated],
    "PATCH": [IsAuthenticated],
}

ChangePasswordPermissions = {
    "POST": [IsAuthenticated],
}

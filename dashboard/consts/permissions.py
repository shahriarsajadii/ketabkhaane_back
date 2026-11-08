from rest_framework.permissions import IsAuthenticated

# همه‌ی اندپوینت‌های داشبورد فقط خواندنی‌اند؛ هر کاربر واردشده می‌تواند ببیند.
DashboardPermissions = {
    "GET": [IsAuthenticated],
}

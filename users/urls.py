from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import *

urlpatterns = [
    path("login/", LoginView.as_view(), name="users.login"),
    path("logout/", LogoutView.as_view(), name="users.logout"),
    path("token/refresh/", TokenRefreshView.as_view(), name="users.token.refresh"),
    path("me/", MeView.as_view(), name="users.me"),
    path("me/password/", ChangePasswordView.as_view(), name="users.me.password"),

    path("", UserListCreate.as_view(), name="users.list-create"),
    path("detail/<int:param>/", UserRetrieveUpdateDelete.as_view(), name="users.retrieve-update-delete"),



]
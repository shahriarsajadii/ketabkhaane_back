from django.contrib.auth import authenticate
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings

from core.authentication import clear_auth_cookies, set_auth_cookies
from core.exceptions import APIError
from core.permissions import MethodPermission
from core.responses import ResponseHelper
from core.views import CreateMixin, DeleteMixin, ListMixin, RetrieveMixin, UpdateMixin

from .consts import (
    ChangePasswordPermissions,
    MePermissions,
    UserListCreatePermissions,
    UserRetrieveUpdateDeletePermissions,
)
from .filters import UserFilter
from .models import User
from .serializers import (
    ChangePasswordSerializer,
    LoginSerializer,
    MeUpdateSerializer,
    UserCreateSerializer,
    UserSerializer,
    UserUpdateSerializer,
)

user_rh = ResponseHelper("کاربر", "کاربران")
auth_rh = ResponseHelper("")


# =====================================================
# Auth
# =====================================================
class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = authenticate(
            request=request,
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
        )
        if user is None:
            raise APIError(field="credentials", message="نام کاربری یا رمز عبور نادرست است.")

        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])

        refresh = RefreshToken.for_user(user)
        response = auth_rh.success(
            message="ورود با موفقیت انجام شد.",
            data=UserSerializer(user).data,
        )
        return set_auth_cookies(response, str(refresh.access_token), str(refresh))


class TokenRefreshView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.COOKIES.get(settings.AUTH_COOKIE_REFRESH)
        if not refresh_token:
            return auth_rh.invalid_token_response()

        serializer = TokenRefreshSerializer(data={"refresh": refresh_token})
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError:
            return auth_rh.invalid_token_response()

        data = serializer.validated_data
        response = auth_rh.success(message="توکن تمدید شد.")

        return set_auth_cookies(response, data["access"], data.get("refresh"))


class LogoutView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.COOKIES.get(settings.AUTH_COOKIE_REFRESH)
        if refresh_token:
            try:
                RefreshToken(refresh_token).blacklist()
            except TokenError:
                pass  # توکن از قبل نامعتبر بوده؛ فقط cookie ها را پاک می‌کنیم

        response = auth_rh.success(message="با موفقیت خارج شدید.")
        return clear_auth_cookies(response)


# =====================================================
# پروفایل خود کاربر
# =====================================================
class MeView(APIView):
    permission_classes = [MethodPermission]
    permission_by_method = MePermissions

    def get(self, request):
        return user_rh.success_get_one_response(UserSerializer(request.user).data)

    def patch(self, request):
        serializer = MeUpdateSerializer(instance=request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return user_rh.success_update_response(data=UserSerializer(user).data)


class ChangePasswordView(APIView):
    permission_classes = [MethodPermission]
    permission_by_method = ChangePasswordPermissions

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password"])
        return user_rh.success_update_response(message="رمز عبور با موفقیت تغییر کرد.")


class UserListCreate(ListMixin, CreateMixin, APIView):
    response_helper = user_rh
    permission_classes = [MethodPermission]
    permission_by_method = UserListCreatePermissions

    queryset = User.objects.all().order_by("-created_at")
    filterset_class = UserFilter

    list_serializer_class = UserSerializer
    create_serializer_class = UserCreateSerializer


class UserRetrieveUpdateDelete(RetrieveMixin, UpdateMixin, DeleteMixin, APIView):
    response_helper = user_rh
    permission_classes = [MethodPermission]
    permission_by_method = UserRetrieveUpdateDeletePermissions

    queryset = User.objects.all()
    lookup_fields = ["id"]

    retrieve_serializer_class = UserSerializer
    update_serializer_class = UserUpdateSerializer

    def validate_delete(self, request, item):
        if item.pk == request.user.pk:
            raise APIError(message="نمی‌توانید حساب خودتان را حذف کنید.")
        return None

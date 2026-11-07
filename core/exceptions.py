from rest_framework.exceptions import (
    AuthenticationFailed,
    ErrorDetail,
    NotAuthenticated,
    PermissionDenied,
    ValidationError,
)
from rest_framework.views import exception_handler
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from core.responses import ResponseHelper


class APIError(Exception):
    """
    خطای کاستوم برای استفاده در view/service:
        raise APIError(field="file", errors=["فایل خالی است"], message="...")
    """

    def __init__(self, field: str = "general", errors=None, message=None, status_code=400):
        self.field = field or "general"
        self.errors = errors or []
        self.message = message or "خطایی رخ داد"
        self.status_code = status_code
        super().__init__(self.message)


def flatten_errors(data):
    if isinstance(data, dict):
        return {k: flatten_errors(v) for k, v in data.items()}
    if isinstance(data, list):
        return [flatten_errors(v) for v in data]
    if isinstance(data, ErrorDetail):
        return str(data)
    return str(data)


# هدرهایی که از پاسخ اصلی DRF نگه داشته می‌شوند (مثلا Retry-After برای throttle)
_KEEP_HEADERS = ("Retry-After", "Allow", "WWW-Authenticate")


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    helper = ResponseHelper("")

    # 1) خطای کاستوم
    if isinstance(exc, APIError):
        return helper.error(
            message=exc.message,
            errors={exc.field: exc.errors} if exc.errors else None,
            status_code=exc.status_code,
        )

    # 2) خطای اعتبارسنجی
    if isinstance(exc, ValidationError):
        return helper.invalid_create_response(
            errors=flatten_errors(exc.detail),
            message="اطلاعات ارسال‌شده معتبر نیست",
        )

    # 3) عدم دسترسی
    if isinstance(exc, PermissionDenied):
        return helper.permission_required_response(message=str(exc.detail))

    # 4) توکن / احراز هویت
    if isinstance(exc, (AuthenticationFailed, InvalidToken, TokenError)):
        return helper.invalid_token_response()

    if isinstance(exc, NotAuthenticated):
        return helper.unauthorized_response()

    # 5) بقیه‌ی خطاهای DRF (404، 405، throttle، ...)
    if response is not None:
        detail = response.data.get("detail") if isinstance(response.data, dict) else None
        new_response = helper.error(
            message=str(detail) if detail else "خطا در سیستم",
            status_code=response.status_code,
        )
        for header in _KEEP_HEADERS:
            if header in response:
                new_response[header] = response[header]
        return new_response

    # 6) خطای پیش‌بینی‌نشده → None تا Django یک 500 واقعی بدهد (و در لاگ ثبت شود)
    return None

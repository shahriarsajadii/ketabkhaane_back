from django.conf import settings
from rest_framework_simplejwt.authentication import JWTAuthentication


class CookieJWTAuthentication(JWTAuthentication):
    """
    توکن access را از cookie می‌خواند (HttpOnly؛ جاوااسکریپت فرانت به آن دسترسی ندارد).
    اگر هدر Authorization: Bearer ... هم فرستاده شود (مثلا برای تست با Postman) همان استفاده می‌شود.

    اگر access منقضی شده باشد 401 با status_code=INVALID_TOKEN برمی‌گردد
    و فرانت باید /api/users/token/refresh/ را صدا بزند و درخواست را تکرار کند.
    """

    def authenticate(self, request):
        header = self.get_header(request)
        if header is not None:
            raw_token = self.get_raw_token(header)
        else:
            raw_token = request.COOKIES.get(settings.AUTH_COOKIE_ACCESS)

        if raw_token is None:
            return None

        validated_token = self.get_validated_token(raw_token)
        return self.get_user(validated_token), validated_token


def set_auth_cookies(response, access, refresh=None):
    jwt = settings.SIMPLE_JWT
    response.set_cookie(
        key=settings.AUTH_COOKIE_ACCESS,
        value=access,
        max_age=int(jwt["ACCESS_TOKEN_LIFETIME"].total_seconds()),
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        path="/",
    )
    if refresh:
        response.set_cookie(
            key=settings.AUTH_COOKIE_REFRESH,
            value=refresh,
            max_age=int(jwt["REFRESH_TOKEN_LIFETIME"].total_seconds()),
            httponly=True,
            secure=settings.AUTH_COOKIE_SECURE,
            samesite=settings.AUTH_COOKIE_SAMESITE,
            path=settings.AUTH_COOKIE_REFRESH_PATH,
        )
    return response


def clear_auth_cookies(response):
    response.delete_cookie(
        settings.AUTH_COOKIE_ACCESS, path="/", samesite=settings.AUTH_COOKIE_SAMESITE
    )
    response.delete_cookie(
        settings.AUTH_COOKIE_REFRESH,
        path=settings.AUTH_COOKIE_REFRESH_PATH,
        samesite=settings.AUTH_COOKIE_SAMESITE,
    )
    return response

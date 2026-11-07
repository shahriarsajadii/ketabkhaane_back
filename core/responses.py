from rest_framework import status
from rest_framework.response import Response


class ResponseHelper:
    def __init__(self, verbose, verbose_plural = None, pagination=None ):
        self.verbose = verbose or ""
        self.verbose_plural = verbose_plural or f"{self.verbose} ها"

    def _base(self , * , is_success , message=None, data=None, errors=None, status_code=status.HTTP_200_OK, **kwargs):
        response = {
            "is_success": is_success,
            "message": message,
            "data": data,
            "errors": errors or {},
        }
        # اضافه شدن همه پارامترهای اضافی از kwargs
        if kwargs:
            response.update(kwargs)

        # حذف فیلدهای اضافی خالی
        response = {k: v for k, v in response.items() if v not in [None, {}, ""]}
        return Response(response, status=status_code)


    def success(self, message=None, data=None, status_code=status.HTTP_200_OK, **kwargs):
        return self._base(
            is_success=True,
            message=message or f"{self.verbose} با موفقیت انجام شد",
            data=data,
            status_code=status_code,
            **kwargs
        )

    # Error Wrapper
    def error(self, message=None, errors=None, status_code=status.HTTP_400_BAD_REQUEST, **kwargs):
        return self._base(
            is_success=False,
            message=message or "خطا در سیستم",
            errors=errors,
            status_code=status_code,
            **kwargs
        )



    # def success_get_all_response(self , data, **kwargs):
    #     return self.success(
    #         message=f"{self.verbose_plural} با موفقیت دریافت شدند",
    #         data=data,
    #         **kwargs
    #     )
    #


    def permission_required_response(self, message=None):
        return Response({
            "is_success": False,
            'message': message or f'شما اجازه انجام این عملیات بر روی {self.verbose} را ندارید ',
            "errors": {"permissions": ["عدم دسترسی"]}
        }, status=status.HTTP_403_FORBIDDEN)

    # GET
    def success_get_all_response(self, pagination=None, data=None, message=None):
        data = {
            "is_success": True,
            "pagination": pagination,
            "message": message or f"عملیات با موفقیت انجام شد",
            "data": data,
            "errors": {},
        }
        if not pagination:
            del data["pagination"]

        return Response(data, status=status.HTTP_200_OK)

    def success_get_one_response(self, data, message=None):
        return Response({
            "is_success": True,
            "message": message or f"{self.verbose} با موفقیت دریافت شد ",
            "data": data or [],
            "errors": {},
        }, status=status.HTTP_200_OK)

    def failed_response(self, errors=None, message=None, status_code=None, data=None):
        response = {
            "is_success": False,
            "message": message or "خطای سیستمی",
            "errors": errors or {},
        }
        if data:
            response.update({"data": data})

        return Response(response, status=status.HTTP_400_BAD_REQUEST)

    def bad_response(self, errors=None, message=None):
        return Response({
            "is_success": False,
            "message": message or "خطا در سیستم",
            "errors": errors or []
        }, status=status.HTTP_400_BAD_REQUEST)

    # POST
    def success_create_response(self, message=None, data=None):
        payload = {
            "is_success": True,
            "message": message or f"{self.verbose} با موفقیت ایجاد شد ",
        }

        if data:
            payload["data"] = data or None

        return Response(payload, status=status.HTTP_201_CREATED)

    def invalid_create_response(self, errors=None, message=None, warnings=None):
        response = {
            "is_success": False,
            "message": message or f"{self.verbose} به دلایلی ایجاد نشد ",
            "errors": errors or []
        }
        if warnings:
            response.update({"warnings": warnings})

        return Response(response, status=status.HTTP_400_BAD_REQUEST)

    #   PATCH / PUT
    def success_update_response(self, message=None, data=None , show_data = None):
        """
        پاسخ موفقیت‌آمیز برای ویرایش (همراه با قابلیت ارسال دیتای جدید)
        """
        response_payload = {
            "is_success": True,
            "message": message or f"{self.verbose} با موفقیت ویرایش شد ",
        }

        # اگر دیتایی پاس داده شده بود (مثلاً لینک فایل آپلود شده)، آن را اضافه کن
        if data is not None:
            response_payload["data"] = data

        return Response(response_payload, status=status.HTTP_200_OK)

    def invalid_update_response(self, errors, message=None, warnings=None):
        response = {
            "is_success": False,
            "message": message or f"{self.verbose} به دلایلی ویرایش نشد ",
            "errors": errors or []
        }
        if warnings:
            response.update({"warnings": warnings})
        return Response(response, status=status.HTTP_400_BAD_REQUEST)

    def success_delete_response(self, message=None):
        response = {
            "is_success": True,
            "message": message or f"{self.verbose} با موفقیت حذف شد"
        }
        return Response(response, status=status.HTTP_200_OK)

    def not_found_response(self, message=None):
        return Response({
            "is_success": False,
            "message": message or f"{self.verbose} با این مشخصات یافت نشد"
        },
            status=status.HTTP_404_NOT_FOUND)

    def deactive_url(self, message=None):
        return Response({
            "is_success": False,
            "message": "این بخش موقتا غیر فعال میباشد !"
        },
            status=status.HTTP_400_BAD_REQUEST)

    def normal_response(self, message=None, is_success=True, status_code=None, data=None, errors=None, status=200):
        return Response({
            "is_success": is_success,
            "message": message or "با موفقیت انجام شد",
            "errors": errors if errors else "",
            "data": data or ""
        }, status=status)

    def unauthorized_response(self, message=None, errors=None):
        """
        پاسخ خطای 401 (عدم احراز هویت)
        """
        return Response({
            "is_success": False,
            "message": message or "لطفا در ابتدا وارد حساب کاربری خود شوید",
            "errors": errors or {"auth": ["احراز هویت انجام نشده است"]}
        }, status=status.HTTP_401_UNAUTHORIZED)

    def invalid_token_response(self):
        return Response({
            "is_success": False,
            "status_code": "INVALID_TOKEN",
            "message": "توکن معتبر نیست",
            "errors": {"token": ["توکن شما منقضی شده یا معتبر نیست."]}
        }, status=401)
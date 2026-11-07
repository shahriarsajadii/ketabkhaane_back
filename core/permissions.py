from rest_framework.permissions import BasePermission, AllowAny, IsAuthenticated
from rest_framework.exceptions import PermissionDenied, NotAuthenticated


class MethodPermission(BasePermission):

    def _get_rules(self, request, view):
        """
        رول هایی که برای هر کلاس ویو نوشته شده ور میگیره
        """
        perm_map = getattr(view, "permission_by_method", None)

        if not perm_map:
            return []

        return perm_map.get(request.method, [])

    def has_permission(self, request, view):
        rules = self._get_rules(request, view)

        for rule in rules:

            if isinstance(rule, dict) and "any" in rule:
                if not any(
                    request.user.has_perm(p)
                    for p in rule["any"]
                ):
                    raise PermissionDenied()

            elif isinstance(rule, type) and issubclass(rule, BasePermission):

                if rule is AllowAny:
                    continue

                permission_instance = rule()

                if not permission_instance.has_permission(request, view):

                    if rule is IsAuthenticated:
                        raise NotAuthenticated()

                    raise PermissionDenied()

            elif isinstance(rule, str):

                if not request.user.is_authenticated:
                    raise NotAuthenticated()

                if not request.user.has_perm(rule):
                    raise PermissionDenied()

            else:
                raise RuntimeError(
                    f"Invalid permission rule: {rule}"
                )

        return True

    def has_object_permission(self, request, view, obj):
        rules = self._get_rules(request, view)

        for rule in rules:

            if isinstance(rule, type) and issubclass(rule, BasePermission):

                permission_instance = rule()

                if not permission_instance.has_object_permission(
                    request,
                    view,
                    obj,
                ):
                    raise PermissionDenied(
                        getattr(
                            permission_instance,
                            "message",
                            "شما اجازه انجام این عملیات را ندارید."
                        )
                    )

        return True
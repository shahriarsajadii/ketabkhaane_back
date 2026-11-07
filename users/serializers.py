from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import User


def _run_password_validators(password, user=None):
    try:
        validate_password(password, user=user)
    except DjangoValidationError as exc:
        raise serializers.ValidationError(list(exc.messages))
    return password


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "name", "is_staff", "is_active", "created_at"]
        read_only_fields = fields


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(trim_whitespace=False)


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    confirm_password = serializers.CharField(write_only=True, trim_whitespace=False)

    class Meta:
        model = User
        fields = ["id", "username", "name", "is_staff", "password", "confirm_password"]

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": ["رمز عبور و تکرار آن یکسان نیستند."]})
        # _run_password_validators(attrs["password"])
        return attrs

    def create(self, validated_data):
        validated_data.pop("confirm_password")
        return User.objects.create_user(**validated_data)

    def to_representation(self, instance):
        return UserSerializer(instance, context=self.context).data


class UserUpdateSerializer(serializers.ModelSerializer):
    """ویرایش کاربر توسط مدیر (رمز اختیاری است؛ اگر بیاید، تغییر می‌کند)"""

    password = serializers.CharField(write_only=True, required=False, trim_whitespace=False)

    class Meta:
        model = User
        fields = ["name", "is_staff", "is_active", "password"]

    def validate_password(self, value):
        return _run_password_validators(value, user=self.instance)

    def validate(self, attrs):
        request = self.context.get("request")
        if request and self.instance and self.instance.pk == request.user.pk:
            if attrs.get("is_active") is False:
                raise serializers.ValidationError({"is_active": ["نمی‌توانید حساب خودتان را غیرفعال کنید."]})
            if attrs.get("is_staff") is False and not request.user.is_superuser:
                raise serializers.ValidationError({"is_staff": ["نمی‌توانید دسترسی مدیر خودتان را بردارید."]})
        return attrs

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        instance = super().update(instance, validated_data)
        if password:
            instance.set_password(password)
            instance.save(update_fields=["password"])
        return instance

    def to_representation(self, instance):
        return UserSerializer(instance, context=self.context).data


class MeUpdateSerializer(serializers.ModelSerializer):
    """کاربر عادی فقط نام خودش را می‌تواند عوض کند"""

    class Meta:
        model = User
        fields = ["name"]


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(trim_whitespace=False)
    new_password = serializers.CharField(trim_whitespace=False)
    confirm_password = serializers.CharField(trim_whitespace=False)

    def validate_old_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("رمز عبور فعلی نادرست است.")
        return value

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": ["رمز جدید و تکرار آن یکسان نیستند."]})
        _run_password_validators(attrs["new_password"], user=self.context["request"].user)
        return attrs

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError("کاربر باید نام کاربری داشته باشد.")

        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)

        user = self.model(username=self.model.normalize_username(username), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser باید is_staff=True باشد.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser باید is_superuser=True باشد.")

        return self.create_user(username, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    کاربرانی که اجازه‌ی ورود به کتابخانه را دارند.
    is_staff=True یعنی «مدیر»: می‌تواند کاربران دیگر را بسازد/ویرایش/حذف کند.
    """

    username = models.CharField(
        max_length=50,
        unique=True,
        validators=[UnicodeUsernameValidator()],
        error_messages={"unique": "این نام کاربری قبلاً ثبت شده است."},
    )
    name = models.CharField(max_length=100)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["name"]

    class Meta:
        db_table = "users"

    def __str__(self):
        return f"{self.name} ({self.username})"

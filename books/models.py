import os
import uuid

from django.db import models
from django.utils import timezone

from authors.models import Author
from categories.models import Category
from core.models import BaseModel
from publishers.models import Publisher


def book_image_path(instance, filename):
    """اسم فایل را رندوم می‌کنیم تا اسم فارسی/تکراری مشکلی نسازد."""
    ext = os.path.splitext(filename)[1].lower() or ".jpg"
    return f"books/{timezone.now():%Y/%m}/{uuid.uuid4().hex}{ext}"

class BookSeries(BaseModel):
    """
    مجموعه‌ی کتاب‌ها، مثلا «لغت‌نامه دهخدا» که از جلد ۱ تا ۲۰ دارد.
    هر جلد یک رکورد Book جداگانه است که به این مجموعه وصل می‌شود (فیلد series + volume_number).
    """
    title = models.CharField("نام مجموعه", max_length=255, unique=True)

    class Meta:
        db_table = "book_series"
        ordering = ["title"]
        verbose_name = "مجموعه کتاب"
        verbose_name_plural = "مجموعه‌های کتاب"

    def __str__(self):
        return self.title


class Book(BaseModel):
    # --- فیلدهای اجباری ---
    title = models.CharField("نام کتاب", max_length=255, db_index=True)
    # یک کتاب می‌تواند چند نویسنده داشته باشد (حداقل یکی، در سریالایزر اجباری می‌شود)
    authors = models.ManyToManyField(Author, related_name="books", blank=True, verbose_name="نویسنده‌ها")
    translator = models.CharField("مترجم", max_length=255 , default="" , blank=True, null=True)
    # «تعداد» و «آدرس قفسه» در BookCopy نگه‌داری می‌شوند (هر نسخه = یک رکورد با یک آدرس)

    # موضوع: از کتابخانه‌ی ملی پر می‌شود (فیلد متنی، جدا از دسته‌بندی‌ای که کاربر خودش انتخاب می‌کند)
    subject = models.TextField("موضوع", blank=True, default="")

    # مجموعه (مثلا دهخدا جلد ۱۸) — اختیاری؛ وقتی کتاب بخشی از یک مجموعه‌ی چندجلدی باشد پر می‌شود
    series = models.ForeignKey(
        BookSeries,
        verbose_name="مجموعه",
        on_delete=models.SET_NULL,
        related_name="books",
        null=True,
        blank=True,
    )
    volume_number = models.PositiveIntegerField("شماره جلد", null=True, blank=True)

    # --- فیلدهای اختیاری ---
    print_series = models.PositiveSmallIntegerField("سری چاپ", null=True, blank=True)
    print_series_date = models.CharField("تاریخ سری چاپ", max_length=50, blank=True, default="")

    dewey_classification = models.CharField("رده‌بندی دیویی", max_length=50, blank=True, default="")
    national_bibliography_number = models.CharField("شماره کتاب‌شناسی ملی", max_length=50, blank=True, default="")
    circulation = models.PositiveIntegerField("شمارگان", null=True, blank=True)
    first_print_date = models.CharField("چاپ اول", max_length=50, blank=True, default="")


    publisher = models.ForeignKey(
        Publisher,
        verbose_name="ناشر",
        on_delete=models.SET_NULL,   # حذف ناشر، کتاب‌هایش را حذف نمی‌کند
        related_name="books",
        null=True,
        blank=True,
    )
    publish_year = models.PositiveSmallIntegerField("سال انتشار", null=True, blank=True)
    isbn = models.CharField("شابک", max_length=30, blank=True, default="")
    page_count = models.PositiveIntegerField("تعداد صفحه", null=True, blank=True)
    note = models.TextField("یادداشت", blank=True, default="")
    image = models.ImageField("عکس", upload_to=book_image_path, null=True, blank=True)

    categories = models.ManyToManyField(Category, related_name="books", blank=True)

    class Meta:
        db_table = "books"
        ordering = ["-created_at", "-id"]
        verbose_name = "کتاب"
        verbose_name_plural = "کتاب‌ها"

    def __str__(self):
        return self.title

    @property
    def count(self):
        # len(.all()) تا اگر prefetch شده باشد، کوئری اضافه نزند
        return len(self.copies.all())


class BookCopy(models.Model):
    """
    هر رکورد = یک نسخه‌ی فیزیکی از کتاب + آدرس نگه‌داری همان نسخه
    مثلا ۳ نسخه از «یادداشت‌های زیرزمینی» → ۳ رکورد با ۳ آدرس.
    """

    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="copies")
    # به شکل «قفسه-ردیف»، مثلا 01-05 یعنی قفسه ۰۱ ردیف ۰۵ (اعتبارسنجی در سریالایزر)
    address = models.CharField("آدرس قفسه", max_length=255)

    # امانت: اگر True باشد، یعنی این نسخه الان دست کسی است (نام در loaned_to)
    is_loaned = models.BooleanField("امانت داده شده", default=False)
    loaned_to = models.CharField("امانت‌گیرنده", max_length=255, blank=True, default="")
    loan_date = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "book_copies"
        ordering = ["id"]
        verbose_name = "نسخه"
        verbose_name_plural = "نسخه‌ها"

    def __str__(self):
        return f"{self.book_id} - {self.address}"
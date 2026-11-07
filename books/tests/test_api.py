import io
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from openpyxl import Workbook, load_workbook
from PIL import Image
from rest_framework.test import APITestCase

from authors.models import Author
from books.models import Book, BookCopy
from categories.models import Category
from publishers.models import Publisher
from users.models import User

URL = "/api/books/"
HEADER = ["نام کتاب", "نویسنده", "مترجم", "تعداد", "آدرس‌ها", "ناشر", "سال انتشار", "شابک", "دسته‌بندی‌ها", "یادداشت"]


def make_author(name="داستایفسکی"):
    return Author.objects.get_or_create(name=name)[0]


def book_payload(**overrides):
    data = {
        "title": "یادداشت‌های زیرزمینی",
        "authors": [make_author().pk],
        "translator": "مترجم نمونه",
        "count": 3,
        "addresses": ["02-01", "02-02", "03-10"],
    }
    data.update(overrides)
    return data


def xlsx_upload(rows, name="books.xlsx"):
    wb = Workbook()
    ws = wb.active
    ws.append(HEADER)
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return SimpleUploadedFile(name, buf.getvalue(), content_type="application/octet-stream")


class BaseAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("ali", "pass1234", name="علی")
        self.client.force_authenticate(self.user)


class BookCrudTests(BaseAPITest):
    def test_requires_login(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(URL).status_code, 401)

    def test_create_with_three_copies(self):
        cat = Category.objects.create(title="رمان")
        publisher = Publisher.objects.create(name="نشر نی")
        res = self.client.post(URL, book_payload(categories=[cat.pk], note="نسخه‌ی اول", publisher=publisher.pk))
        self.assertEqual(res.status_code, 201, res.data)
        data = res.data["data"]
        self.assertEqual(data["count"], 3)
        self.assertEqual(data["addresses"], book_payload()["addresses"])
        self.assertEqual(data["categories"], [{"id": cat.pk, "title": "رمان"}])
        self.assertEqual(data["authors"], [{"id": make_author().pk, "name": "داستایفسکی"}])
        self.assertEqual(data["publisher"], {"id": publisher.pk, "name": "نشر نی"})
        self.assertEqual(data["note"], "نسخه‌ی اول")
        self.assertEqual(data["created_by"], "علی")
        self.assertEqual(BookCopy.objects.count(), 3)

    def test_count_defaults_to_number_of_addresses(self):
        payload = book_payload(addresses=["01-01"])
        del payload["count"]
        res = self.client.post(URL, payload)
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["data"]["count"], 1)

    def test_count_must_match_addresses(self):
        res = self.client.post(URL, book_payload(count=2))
        self.assertEqual(res.status_code, 400)
        self.assertIn("addresses", res.data["errors"])
        self.assertEqual(Book.objects.count(), 0)

    def test_required_fields(self):
        res = self.client.post(URL, {"title": "فقط نام"})
        self.assertEqual(res.status_code, 400)
        # مترجم اختیاری است (default="")؛ نویسنده و آدرس اجباری‌اند
        for field in ("authors", "addresses"):
            self.assertIn(field, res.data["errors"])
        self.assertNotIn("translator", res.data["errors"])

    def test_blank_address_rejected(self):
        res = self.client.post(URL, book_payload(count=1, addresses=["   "]))
        self.assertEqual(res.status_code, 400)

    def test_at_least_one_author(self):
        res = self.client.post(URL, book_payload(authors=[]))
        self.assertEqual(res.status_code, 400)
        self.assertIn("authors", res.data["errors"])
        res = self.client.post(URL, book_payload(authors=[99999]))
        self.assertEqual(res.status_code, 400)
        self.assertIn("authors", res.data["errors"])

    def test_multiple_authors_and_update(self):
        a1, a2 = make_author("الف"), make_author("ب")
        res = self.client.post(URL, book_payload(authors=[a1.pk, a2.pk]))
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual({a["name"] for a in res.data["data"]["authors"]}, {"الف", "ب"})

        res = self.client.patch(f"{URL}detail/{res.data['data']['id']}/", {"authors": [a2.pk]})
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual([a["id"] for a in res.data["data"]["authors"]], [a2.pk])

    def test_publisher_is_optional_and_nullable(self):
        res = self.client.post(URL, book_payload())
        self.assertEqual(res.status_code, 201, res.data)
        self.assertIsNone(res.data["data"]["publisher"])

        publisher = Publisher.objects.create(name="نشر نی")
        url = f"{URL}detail/{res.data['data']['id']}/"
        res = self.client.patch(url, {"publisher": publisher.pk})
        self.assertEqual(res.data["data"]["publisher"]["id"], publisher.pk)
        res = self.client.patch(url, {"publisher": None})
        self.assertIsNone(res.data["data"]["publisher"])

        res = self.client.patch(url, {"publisher": 99999})
        self.assertEqual(res.status_code, 400)
        self.assertIn("publisher", res.data["errors"])

    def test_deleting_publisher_keeps_books(self):
        publisher = Publisher.objects.create(name="نشر نی")
        book_id = self.client.post(URL, book_payload(publisher=publisher.pk)).data["data"]["id"]
        publisher.delete()
        self.assertTrue(Book.objects.filter(pk=book_id, publisher__isnull=True).exists())

    def test_duplicate_book_rejected(self):
        self.assertEqual(self.client.post(URL, book_payload()).status_code, 201)
        res = self.client.post(URL, book_payload())
        self.assertEqual(res.status_code, 400)
        self.assertIn("title", res.data["errors"])
        # ناشر متفاوت = نسخه‌ی چاپ دیگر → مجاز
        other = Publisher.objects.create(name="نشر دیگر")
        res = self.client.post(URL, book_payload(publisher=other.pk))
        self.assertEqual(res.status_code, 201, res.data)
        # نویسنده‌ی متفاوت → مجاز
        res = self.client.post(URL, book_payload(authors=[make_author("کس دیگر").pk]))
        self.assertEqual(res.status_code, 201, res.data)


class BookAddressTests(BaseAPITest):
    def test_address_is_normalized(self):
        res = self.client.post(URL, book_payload(count=3, addresses=["1-5", "۰۲ - ۱۰", "50-50"]))
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["data"]["addresses"], ["01-05", "02-10", "50-50"])

    def test_invalid_addresses_report_their_index(self):
        res = self.client.post(URL, book_payload(count=3, addresses=["01-05", "51-01", "قفسه ۲"]))
        self.assertEqual(res.status_code, 400)
        # کلید خطا = ایندکس نسخه (در JSON رشته می‌شود)
        indexes = {str(k) for k in res.data["errors"]["addresses"]}
        self.assertEqual(indexes, {"1", "2"})
        self.assertEqual(Book.objects.count(), 0)

    def test_range_limits(self):
        for bad in ("00-01", "01-00", "51-01", "01-51"):
            res = self.client.post(URL, book_payload(count=1, addresses=[bad]))
            self.assertEqual(res.status_code, 400, bad)
        self.assertEqual(self.client.post(URL, book_payload(count=1, addresses=["50-50"])).status_code, 201)

    def test_patch_addresses_validated(self):
        book_id = self.client.post(URL, book_payload()).data["data"]["id"]
        res = self.client.patch(f"{URL}detail/{book_id}/", {"addresses": ["حرف", "01-02", "01-03"]})
        self.assertEqual(res.status_code, 400)

    def test_retrieve_update_addresses_shrink_and_grow(self):
        book_id = self.client.post(URL, book_payload()).data["data"]["id"]
        url = f"{URL}detail/{book_id}/"

        res = self.client.patch(url, {"addresses": ["09-01", "08-01"]})
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["data"]["addresses"], ["09-01", "08-01"])
        self.assertEqual(res.data["data"]["count"], 2)
        self.assertEqual(BookCopy.objects.filter(book_id=book_id).count(), 2)

        res = self.client.patch(url, {"addresses": ["01-01", "01-02", "01-03", "01-04"], "count": 4})
        self.assertEqual(res.data["data"]["addresses"], ["01-01", "01-02", "01-03", "01-04"])

        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["data"]["count"], 4)

    def test_patch_count_alone_must_match_existing(self):
        book_id = self.client.post(URL, book_payload()).data["data"]["id"]
        res = self.client.patch(f"{URL}detail/{book_id}/", {"count": 5})
        self.assertEqual(res.status_code, 400)

    def test_patch_other_fields_keeps_copies(self):
        book_id = self.client.post(URL, book_payload()).data["data"]["id"]
        res = self.client.patch(f"{URL}detail/{book_id}/", {"note": "یادداشت جدید"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["data"]["note"], "یادداشت جدید")
        self.assertEqual(res.data["data"]["count"], 3)

    def test_update_categories(self):
        c1 = Category.objects.create(title="a")
        c2 = Category.objects.create(title="b")
        book_id = self.client.post(URL, book_payload(categories=[c1.pk])).data["data"]["id"]
        res = self.client.patch(f"{URL}detail/{book_id}/", {"categories": [c2.pk]})
        self.assertEqual([c["id"] for c in res.data["data"]["categories"]], [c2.pk])

    def test_not_found(self):
        self.assertEqual(self.client.get(f"{URL}detail/999/").status_code, 404)

    def test_delete_and_bulk_delete(self):
        b1 = self.client.post(URL, book_payload()).data["data"]["id"]
        b2 = self.client.post(URL, book_payload(title="دوم")).data["data"]["id"]
        b3 = self.client.post(URL, book_payload(title="سوم")).data["data"]["id"]

        self.assertEqual(self.client.delete(f"{URL}detail/{b1}/").status_code, 200)
        self.assertEqual(BookCopy.objects.filter(book_id=b1).count(), 0)

        res = self.client.delete(URL, {"items": [b2, b3]})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(Book.objects.count(), 0)


class BookListFilterTests(BaseAPITest):
    def setUp(self):
        super().setUp()
        self.novel = Category.objects.create(title="رمان")
        self.poem = Category.objects.create(title="شعر")
        self.dosto = make_author("داستایفسکی")
        self.hafez = make_author("حافظ")
        self.pub = Publisher.objects.create(name="نشر نی")
        self.client.post(URL, book_payload(categories=[self.novel.pk]))
        self.client.post(URL, book_payload(
            title="دیوان حافظ", authors=[self.hafez.pk], translator="ندارد", count=1,
            addresses=["07-12"], categories=[self.poem.pk, self.novel.pk],
            publisher=self.pub.pk, publish_year=1398,
        ))

    def titles(self, **params):
        res = self.client.get(URL, params)
        self.assertEqual(res.status_code, 200)
        return [b["title"] for b in res.data["data"]]

    def test_pagination_block(self):
        res = self.client.get(URL, {"page_size": 1})
        self.assertEqual(len(res.data["data"]), 1)
        self.assertEqual(res.data["pagination"]["total_items"], 2)

    def test_search_in_title_author_publisher_and_address(self):
        self.assertEqual(self.titles(search="حافظ"), ["دیوان حافظ"])
        self.assertEqual(self.titles(search="داستایفسکی"), ["یادداشت‌های زیرزمینی"])
        self.assertEqual(self.titles(search="نشر نی"), ["دیوان حافظ"])
        self.assertEqual(self.titles(search="07-12"), ["دیوان حافظ"])

    def test_filter_by_address(self):
        self.assertEqual(self.titles(address="02-"), ["یادداشت‌های زیرزمینی"])
        self.assertEqual(self.titles(address="03-10"), ["یادداشت‌های زیرزمینی"])

    def test_filter_by_author_and_publisher(self):
        self.assertEqual(self.titles(author=f"{self.hafez.pk}"), ["دیوان حافظ"])
        self.assertEqual(len(self.titles(author=f"{self.hafez.pk},{self.dosto.pk}")), 2)
        self.assertEqual(self.titles(author_name="حاف"), ["دیوان حافظ"])
        self.assertEqual(self.titles(publisher=f"{self.pub.pk}"), ["دیوان حافظ"])
        self.assertEqual(self.titles(publisher_name="نی"), ["دیوان حافظ"])
        self.assertEqual(self.titles(publish_year=1398), ["دیوان حافظ"])

    def test_filter_by_category_no_duplicates(self):
        self.assertEqual(len(self.titles(category=f"{self.novel.pk}")), 2)
        self.assertEqual(self.titles(category=f"{self.poem.pk}"), ["دیوان حافظ"])
        self.assertEqual(len(self.titles(category=f"{self.poem.pk},{self.novel.pk}")), 2)

    def test_ordering(self):
        self.assertEqual(self.titles(ordering="title"), sorted(self.titles()))


class BookImageTests(BaseAPITest):
    def setUp(self):
        super().setUp()
        self.media = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media)
        self.override.enable()
        self.book_id = self.client.post(URL, book_payload()).data["data"]["id"]

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media, ignore_errors=True)

    @staticmethod
    def png(name="cover.png"):
        buf = io.BytesIO()
        Image.new("RGB", (10, 10), "red").save(buf, "PNG")
        return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")

    def test_upload_replace_delete(self):
        url = f"{URL}{self.book_id}/image/"

        res = self.client.post(url, {"image": self.png()}, format="multipart")
        self.assertEqual(res.status_code, 200, res.data)
        first_path = Book.objects.get(pk=self.book_id).image.path

        detail = self.client.get(f"{URL}detail/{self.book_id}/")
        self.assertTrue(detail.data["data"]["image"].startswith("http"))

        res = self.client.post(url, {"image": self.png("other.png")}, format="multipart")
        self.assertEqual(res.status_code, 200)
        book = Book.objects.get(pk=self.book_id)
        self.assertNotEqual(book.image.path, first_path)

        res = self.client.delete(url)
        self.assertEqual(res.status_code, 200)
        self.assertFalse(Book.objects.get(pk=self.book_id).image)

    def test_rejects_non_image(self):
        fake = SimpleUploadedFile("x.png", b"not an image", content_type="image/png")
        res = self.client.post(f"{URL}{self.book_id}/image/", {"image": fake}, format="multipart")
        self.assertEqual(res.status_code, 400)

    def test_unknown_book(self):
        res = self.client.post(f"{URL}999/image/", {"image": self.png()}, format="multipart")
        self.assertEqual(res.status_code, 404)


class BookExcelTests(BaseAPITest):
    def test_import_all_valid_creates_books_copies_and_categories(self):
        upload = xlsx_upload([
            ["یادداشت‌های زیرزمینی", "داستایفسکی", "مترجم", 3, "01-01 | 01-02 | 01-03", "نشر", 1398, "", "رمان، کلاسیک", "خوب"],
            ["دیوان حافظ", "حافظ", "ندارد", None, "07-07", None, None, None, "شعر", None],
        ])
        res = self.client.post(f"{URL}import/", {"file": upload}, format="multipart")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["data"]["created"], 2)
        self.assertEqual(Book.objects.count(), 2)
        self.assertEqual(BookCopy.objects.count(), 4)
        self.assertEqual(set(Category.objects.values_list("title", flat=True)), {"رمان", "کلاسیک", "شعر"})
        book = Book.objects.get(title="یادداشت‌های زیرزمینی")
        self.assertEqual([c.address for c in book.copies.all()], ["01-01", "01-02", "01-03"])
        self.assertEqual(book.created_by, self.user)
        # نویسنده و ناشر هم خودکار ساخته و وصل می‌شوند
        self.assertEqual(set(Author.objects.values_list("name", flat=True)), {"داستایفسکی", "حافظ"})
        self.assertEqual(book.publisher.name, "نشر")
        self.assertEqual([a.name for a in book.authors.all()], ["داستایفسکی"])
        self.assertIsNone(Book.objects.get(title="دیوان حافظ").publisher)

    def test_import_reuses_existing_author_and_publisher(self):
        existing_author = make_author("داستایفسکی")
        existing_publisher = Publisher.objects.create(name="نشر")
        upload = xlsx_upload([
            ["الف", " داستایفسکی ", "ج", 1, "01-01", "نشر", None, None, None, None],
            ["ب", "داستایفسکی | حافظ", "ج", 1, "01-02", "نشر", None, None, None, None],
        ])
        res = self.client.post(f"{URL}import/", {"file": upload}, format="multipart")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(Author.objects.count(), 2)
        self.assertEqual(Publisher.objects.count(), 1)
        self.assertEqual(Book.objects.get(title="ب").authors.count(), 2)
        self.assertIn(existing_author, Book.objects.get(title="الف").authors.all())
        self.assertEqual(Book.objects.get(title="الف").publisher, existing_publisher)

    def test_import_rejects_bad_address_format(self):
        upload = xlsx_upload([["الف", "ب", "ج", 1, "قفسه ۲", None, None, None, None, None]])
        res = self.client.post(f"{URL}import/", {"file": upload}, format="multipart")
        self.assertEqual(res.status_code, 400)
        self.assertIn("addresses", res.data["errors"]["rows"][0]["errors"])
        self.assertEqual(Book.objects.count(), 0)

    def test_import_all_or_nothing_by_default(self):
        upload = xlsx_upload([
            ["کتاب سالم", "الف", "ب", 1, "01-01", None, None, None, "تازه", None],
            ["بدون نویسنده", None, "ب", 1, "01-02", None, None, None, None, None],
        ])
        res = self.client.post(f"{URL}import/", {"file": upload}, format="multipart")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data["errors"]["rows"][0]["row"], 3)
        self.assertIn("authors", res.data["errors"]["rows"][0]["errors"])
        self.assertEqual(Book.objects.count(), 0)
        self.assertEqual(Category.objects.count(), 0)   # دسته‌ی ساخته‌شده هم برگشت خورده
        self.assertEqual(Author.objects.count(), 0)     # نویسنده‌ی ساخته‌شده هم برگشت خورده

    def test_import_skip_invalid(self):
        upload = xlsx_upload([
            ["کتاب سالم", "الف", "ب", 1, "01-01", None, None, None, None, None],
            ["بدون آدرس", "الف", "ب", 1, None, None, None, None, None, None],
            ["تعداد نامعتبر", "الف", "ب", "سه تا", "01-01", None, None, None, None, None],
        ])
        res = self.client.post(f"{URL}import/?skip_invalid=true", {"file": upload}, format="multipart")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["data"]["created"], 1)
        self.assertEqual([f["row"] for f in res.data["data"]["failed"]], [3, 4])
        self.assertEqual(Book.objects.count(), 1)

    def test_import_duplicates_inside_file_and_against_db(self):
        Book.objects.create(title="موجود", translator="ب").authors.add(make_author("الف"))
        upload = xlsx_upload([
            ["موجود", "الف", "ب", 1, "01-01", None, None, None, None, None],
            ["جدید", "الف", "ب", 1, "01-02", None, None, None, None, None],
            ["جدید", "الف", "ب", 1, "01-03", None, None, None, None, None],
        ])
        res = self.client.post(f"{URL}import/?skip_invalid=1", {"file": upload}, format="multipart")
        self.assertEqual(res.data["data"]["created"], 1)
        self.assertEqual([f["row"] for f in res.data["data"]["failed"]], [2, 4])

    def test_import_rejects_bad_files(self):
        res = self.client.post(f"{URL}import/", {"file": SimpleUploadedFile("a.xls", b"x")}, format="multipart")
        self.assertEqual(res.status_code, 400)
        res = self.client.post(f"{URL}import/", {"file": SimpleUploadedFile("a.xlsx", b"not excel")}, format="multipart")
        self.assertEqual(res.status_code, 400)
        res = self.client.post(f"{URL}import/", {}, format="multipart")
        self.assertEqual(res.status_code, 400)

    def test_template_download(self):
        res = self.client.get(f"{URL}import/template/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("spreadsheetml", res["Content-Type"])
        wb = load_workbook(io.BytesIO(res.content))
        self.assertEqual(wb.sheetnames[0], "کتاب‌ها")

    def test_export_with_filter_and_roundtrip(self):
        self.client.post(URL, book_payload())
        self.client.post(URL, book_payload(title="دیوان حافظ", authors=[make_author("حافظ").pk], translator="ندارد",
                                           count=1, addresses=["07-07"]))

        res = self.client.get(f"{URL}export/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("spreadsheetml", res["Content-Type"])
        rows = list(load_workbook(io.BytesIO(res.content)).active.iter_rows(values_only=True))
        self.assertEqual(len(rows), 3)  # عنوان + دو کتاب
        self.assertEqual(rows[0][0], "نام کتاب")

        res = self.client.get(f"{URL}export/", {"search": "حافظ"})
        rows = list(load_workbook(io.BytesIO(res.content)).active.iter_rows(values_only=True))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][0], "دیوان حافظ")

    def test_exported_file_can_be_imported_elsewhere(self):
        self.client.post(URL, book_payload())
        exported = self.client.get(f"{URL}export/").content
        Book.objects.all().delete()

        upload = SimpleUploadedFile("books.xlsx", exported)
        res = self.client.post(f"{URL}import/", {"file": upload}, format="multipart")
        self.assertEqual(res.status_code, 201, res.data)
        book = Book.objects.get()
        self.assertEqual(book.count, 3)
        self.assertEqual([c.address for c in book.copies.all()], book_payload()["addresses"])

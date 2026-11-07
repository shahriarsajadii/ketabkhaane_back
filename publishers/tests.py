import io
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework.test import APITestCase

from authors.models import Author
from books.models import Book
from users.models import User

from .models import Publisher

URL = "/api/publishers/"


def png(name="logo.png"):
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), "blue").save(buf, "PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


class PublisherTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("ali", "pass1234", name="علی")
        self.client.force_authenticate(self.user)

    def test_requires_login(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(URL).status_code, 401)

    def test_create_and_duplicate(self):
        res = self.client.post(URL, {"name": "نشر نی"})
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["data"]["name"], "نشر نی")
        self.assertEqual(res.data["data"]["books_count"], 0)
        self.assertIsNone(res.data["data"]["image"])
        self.assertEqual(Publisher.objects.get().created_by, self.user)

        res = self.client.post(URL, {"name": "  نشر   نی "})
        self.assertEqual(res.status_code, 400)
        self.assertIn("name", res.data["errors"])

    def test_name_required(self):
        res = self.client.post(URL, {"name": "   "})
        self.assertEqual(res.status_code, 400)
        self.assertIn("name", res.data["errors"])
        res = self.client.post(URL, {})
        self.assertEqual(res.status_code, 400)

    def test_list_filter_pagination_and_books_count(self):
        ni = Publisher.objects.create(name="نشر نی")
        Publisher.objects.create(name="انتشارات مرکز")
        Book.objects.create(title="الف", translator="ب", publisher=ni)

        res = self.client.get(URL)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["pagination"]["total_items"], 2)

        res = self.client.get(URL, {"search": "نی"})
        self.assertEqual([p["name"] for p in res.data["data"]], ["نشر نی"])
        self.assertEqual(res.data["data"][0]["books_count"], 1)

        res = self.client.get(URL, {"name": "مرکز"})
        self.assertEqual([p["name"] for p in res.data["data"]], ["انتشارات مرکز"])

        res = self.client.get(URL, {"ordering": "-books_count"})
        self.assertEqual(res.data["data"][0]["name"], "نشر نی")

        res = self.client.get(URL, {"page_size": 1})
        self.assertEqual(len(res.data["data"]), 1)

    def test_update_and_delete_keep_books(self):
        pub = Publisher.objects.create(name="نشر نی")
        book = Book.objects.create(title="الف", translator="ب", publisher=pub)

        res = self.client.patch(f"{URL}detail/{pub.pk}/", {"name": "نشر نی ۲"})
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["data"]["name"], "نشر نی ۲")

        # تغییر به اسم خودش مشکلی ندارد، به اسم ناشر دیگر خطا می‌دهد
        Publisher.objects.create(name="دیگری")
        self.assertEqual(self.client.patch(f"{URL}detail/{pub.pk}/", {"name": "نشر نی ۲"}).status_code, 200)
        self.assertEqual(self.client.patch(f"{URL}detail/{pub.pk}/", {"name": "دیگری"}).status_code, 400)

        self.assertEqual(self.client.get(f"{URL}detail/{pub.pk}/").status_code, 200)
        self.assertEqual(self.client.delete(f"{URL}detail/{pub.pk}/").status_code, 200)
        book.refresh_from_db()
        self.assertIsNone(book.publisher)
        self.assertEqual(self.client.get(f"{URL}detail/{pub.pk}/").status_code, 404)

    def test_bulk_delete(self):
        p1 = Publisher.objects.create(name="a1")
        p2 = Publisher.objects.create(name="a2")
        res = self.client.delete(URL, {"items": [p1.pk, p2.pk]})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(Publisher.objects.count(), 0)


class PublisherImageTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("ali", "pass1234", name="علی")
        self.client.force_authenticate(self.user)
        self.media = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media)
        self.override.enable()
        self.pub = Publisher.objects.create(name="نشر نی")

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media, ignore_errors=True)

    def test_upload_replace_delete(self):
        url = f"{URL}{self.pub.pk}/image/"
        res = self.client.post(url, {"image": png()}, format="multipart")
        self.assertEqual(res.status_code, 200, res.data)
        self.pub.refresh_from_db()
        first = self.pub.image.path

        detail = self.client.get(f"{URL}detail/{self.pub.pk}/")
        self.assertTrue(detail.data["data"]["image"].startswith("http"))

        res = self.client.post(url, {"image": png("b.png")}, format="multipart")
        self.assertEqual(res.status_code, 200)
        self.pub.refresh_from_db()
        self.assertNotEqual(self.pub.image.path, first)

        self.assertEqual(self.client.delete(url).status_code, 200)
        self.pub.refresh_from_db()
        self.assertFalse(self.pub.image)

    def test_rejects_non_image_and_unknown(self):
        fake = SimpleUploadedFile("x.png", b"not an image", content_type="image/png")
        res = self.client.post(f"{URL}{self.pub.pk}/image/", {"image": fake}, format="multipart")
        self.assertEqual(res.status_code, 400)
        res = self.client.post(f"{URL}999/image/", {"image": png()}, format="multipart")
        self.assertEqual(res.status_code, 404)

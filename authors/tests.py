import io
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework.test import APITestCase

from books.models import Book
from users.models import User

from .models import Author

URL = "/api/authors/"


def png(name="photo.png"):
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), "green").save(buf, "PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


def make_book(title, *authors):
    book = Book.objects.create(title=title, translator="ب")
    book.authors.set(authors)
    return book


class AuthorTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("ali", "pass1234", name="علی")
        self.client.force_authenticate(self.user)

    def test_requires_login(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(URL).status_code, 401)

    def test_create_only_name_description_is_optional(self):
        res = self.client.post(URL, {"name": "حافظ"})
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["data"]["description"], "")
        self.assertIsNone(res.data["data"]["image"])

        res = self.client.post(URL, {"name": "سعدی", "description": "شاعر شیراز"})
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["data"]["description"], "شاعر شیراز")

    def test_name_required_and_unique(self):
        self.assertEqual(self.client.post(URL, {}).status_code, 400)
        self.assertEqual(self.client.post(URL, {"name": " "}).status_code, 400)
        self.client.post(URL, {"name": "حافظ"})
        res = self.client.post(URL, {"name": "  حافظ "})
        self.assertEqual(res.status_code, 400)
        self.assertIn("name", res.data["errors"])

    def test_list_filters_pagination_books_count(self):
        hafez = Author.objects.create(name="حافظ", description="شاعر غزل")
        Author.objects.create(name="سعدی", description="شاعر گلستان")
        make_book("دیوان", hafez)

        res = self.client.get(URL)
        self.assertEqual(res.data["pagination"]["total_items"], 2)

        res = self.client.get(URL, {"search": "حاف"})
        self.assertEqual([a["name"] for a in res.data["data"]], ["حافظ"])
        self.assertEqual(res.data["data"][0]["books_count"], 1)

        # search روی توضیحات هم کار می‌کند، name فقط روی نام
        self.assertEqual(len(self.client.get(URL, {"search": "گلستان"}).data["data"]), 1)
        self.assertEqual(len(self.client.get(URL, {"name": "گلستان"}).data["data"]), 0)
        self.assertEqual(len(self.client.get(URL, {"description": "غزل"}).data["data"]), 1)

        res = self.client.get(URL, {"ordering": "-books_count"})
        self.assertEqual(res.data["data"][0]["name"], "حافظ")

    def test_update(self):
        author = Author.objects.create(name="حافظ")
        res = self.client.patch(f"{URL}detail/{author.pk}/", {"description": "توضیح جدید"})
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["data"]["description"], "توضیح جدید")
        self.assertEqual(res.data["data"]["name"], "حافظ")
        Author.objects.create(name="سعدی")
        self.assertEqual(self.client.patch(f"{URL}detail/{author.pk}/", {"name": "سعدی"}).status_code, 400)

    def test_delete_blocked_when_author_has_books(self):
        author = Author.objects.create(name="حافظ")
        make_book("دیوان", author)

        res = self.client.delete(f"{URL}detail/{author.pk}/")
        self.assertEqual(res.status_code, 400)
        self.assertTrue(Author.objects.filter(pk=author.pk).exists())

        res = self.client.delete(URL, {"items": [author.pk]})
        self.assertEqual(res.status_code, 400)
        self.assertTrue(Author.objects.filter(pk=author.pk).exists())

    def test_delete_and_bulk_delete_without_books(self):
        a1 = Author.objects.create(name="a1")
        a2 = Author.objects.create(name="a2")
        a3 = Author.objects.create(name="a3")
        self.assertEqual(self.client.delete(f"{URL}detail/{a1.pk}/").status_code, 200)
        res = self.client.delete(URL, {"items": [a2.pk, a3.pk]})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(Author.objects.count(), 0)


class AuthorImageTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("ali", "pass1234", name="علی")
        self.client.force_authenticate(self.user)
        self.media = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media)
        self.override.enable()
        self.author = Author.objects.create(name="حافظ")

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media, ignore_errors=True)

    def test_upload_replace_delete(self):
        url = f"{URL}{self.author.pk}/image/"
        self.assertEqual(self.client.post(url, {"image": png()}, format="multipart").status_code, 200)
        self.author.refresh_from_db()
        self.assertTrue(self.author.image)
        self.assertEqual(self.client.delete(url).status_code, 200)
        self.author.refresh_from_db()
        self.assertFalse(self.author.image)

    def test_rejects_non_image_and_unknown(self):
        fake = SimpleUploadedFile("x.png", b"nope", content_type="image/png")
        res = self.client.post(f"{URL}{self.author.pk}/image/", {"image": fake}, format="multipart")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(self.client.post(f"{URL}999/image/", {"image": png()}, format="multipart").status_code, 404)

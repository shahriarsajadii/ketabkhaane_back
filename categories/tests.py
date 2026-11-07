from rest_framework.test import APITestCase

from books.models import Book
from users.models import User

from .models import Category


class CategoryTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("ali", "pass1234", name="علی")
        self.client.force_authenticate(self.user)

    def test_requires_login(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/categories/").status_code, 401)

    def test_create_and_duplicate(self):
        res = self.client.post("/api/categories/", {"title": "رمان"})
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["data"]["title"], "رمان")
        self.assertEqual(res.data["data"]["books_count"], 0)

        res = self.client.post("/api/categories/", {"title": "  رمان "})
        self.assertEqual(res.status_code, 400)
        self.assertIn("title", res.data["errors"])

    def test_list_has_books_count_and_is_not_paginated(self):
        cat = Category.objects.create(title="شعر", created_by=self.user, updated_by=self.user)
        book = Book.objects.create(title="الف", author="ب", translator="ج")
        book.categories.add(cat)

        res = self.client.get("/api/categories/")
        self.assertEqual(res.status_code, 200)
        self.assertNotIn("pagination", res.data)
        self.assertEqual(res.data["data"][0]["books_count"], 1)

    def test_update_and_delete_keep_books(self):
        cat = Category.objects.create(title="شعر", created_by=self.user, updated_by=self.user)
        book = Book.objects.create(title="الف", author="ب", translator="ج")
        book.categories.add(cat)

        res = self.client.patch(f"/api/categories/detail/{cat.pk}/", {"title": "شعر نو"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["data"]["title"], "شعر نو")

        res = self.client.delete(f"/api/categories/detail/{cat.pk}/")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(Book.objects.filter(pk=book.pk).exists())

    def test_bulk_delete(self):
        c1 = Category.objects.create(title="a1")
        c2 = Category.objects.create(title="a2")
        res = self.client.delete("/api/categories/", {"items": [c1.pk, c2.pk]})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(Category.objects.count(), 0)

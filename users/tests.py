from django.core.cache import cache
from rest_framework.test import APITestCase

from .models import User


class AuthTests(APITestCase):
    def setUp(self):
        cache.clear()  # شمارنده‌ی throttle لاگین
        self.user = User.objects.create_user("ali", "pass1234", name="علی")

    def test_login_sets_httponly_cookies(self):
        res = self.client.post("/api/users/login/", {"username": "ali", "password": "pass1234"})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data["is_success"])
        self.assertEqual(res.data["data"]["username"], "ali")
        self.assertTrue(res.cookies["access_token"]["httponly"])
        self.assertTrue(res.cookies["refresh_token"]["httponly"])

    def test_login_wrong_password(self):
        res = self.client.post("/api/users/login/", {"username": "ali", "password": "wrong"})
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.data["is_success"])

    def test_inactive_user_cannot_login(self):
        self.user.is_active = False
        self.user.save()
        res = self.client.post("/api/users/login/", {"username": "ali", "password": "pass1234"})
        self.assertEqual(res.status_code, 400)

    def test_me_with_cookie_and_without(self):
        self.assertEqual(self.client.get("/api/users/me/").status_code, 401)
        self.client.post("/api/users/login/", {"username": "ali", "password": "pass1234"})
        res = self.client.get("/api/users/me/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["data"]["username"], "ali")

    def test_stale_cookie_does_not_block_login(self):
        self.client.cookies["access_token"] = "garbage"
        res = self.client.post("/api/users/login/", {"username": "ali", "password": "pass1234"})
        self.assertEqual(res.status_code, 200)

    def test_refresh_and_logout(self):
        self.client.post("/api/users/login/", {"username": "ali", "password": "pass1234"})
        res = self.client.post("/api/users/token/refresh/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("access_token", res.cookies)

        res = self.client.post("/api/users/logout/")
        self.assertEqual(res.status_code, 200)
        res = self.client.post("/api/users/token/refresh/")
        self.assertEqual(res.status_code, 401)

    def test_change_password(self):
        self.client.force_authenticate(self.user)
        res = self.client.post("/api/users/me/password/", {
            "old_password": "bad", "new_password": "newpass99", "confirm_password": "newpass99",
        })
        self.assertEqual(res.status_code, 400)

        res = self.client.post("/api/users/me/password/", {
            "old_password": "pass1234", "new_password": "newpass99", "confirm_password": "newpass99",
        })
        self.assertEqual(res.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("newpass99"))


class UserManagementTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("ali", "pass1234", name="علی")
        self.manager = User.objects.create_user("boss", "pass1234", name="مدیر", is_staff=True)

    def test_regular_user_cannot_manage_users(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get("/api/users/").status_code, 403)
        self.assertEqual(self.client.post("/api/users/", {}).status_code, 403)

    def test_manager_creates_lists_updates_deletes(self):
        self.client.force_authenticate(self.manager)

        res = self.client.post("/api/users/", {
            "username": "sara", "name": "سارا", "password": "pass1234", "confirm_password": "pass1234",
        })
        self.assertEqual(res.status_code, 201)
        new_id = res.data["data"]["id"]
        self.assertTrue(User.objects.get(username="sara").check_password("pass1234"))
        self.assertNotIn("password", res.data["data"])

        res = self.client.get("/api/users/", {"search": "سارا"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data["data"]), 1)

        res = self.client.patch(f"/api/users/detail/{new_id}/", {"name": "سارا احمدی", "password": "another99"})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(User.objects.get(pk=new_id).check_password("another99"))

        res = self.client.delete(f"/api/users/detail/{new_id}/")
        self.assertEqual(res.status_code, 200)
        self.assertFalse(User.objects.filter(pk=new_id).exists())

    def test_password_mismatch_and_duplicate_username(self):
        self.client.force_authenticate(self.manager)
        res = self.client.post("/api/users/", {
            "username": "x1", "name": "x", "password": "pass1234", "confirm_password": "different",
        })
        self.assertEqual(res.status_code, 400)
        res = self.client.post("/api/users/", {
            "username": "ali", "name": "x", "password": "pass1234", "confirm_password": "pass1234",
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("username", res.data["errors"])

    def test_manager_cannot_delete_or_deactivate_self(self):
        self.client.force_authenticate(self.manager)
        self.assertEqual(self.client.delete(f"/api/users/detail/{self.manager.pk}/").status_code, 400)
        res = self.client.patch(f"/api/users/detail/{self.manager.pk}/", {"is_active": False})
        self.assertEqual(res.status_code, 400)

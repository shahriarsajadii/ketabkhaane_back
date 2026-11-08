from rest_framework.test import APITestCase

from authors.models import Author
from books.models import Book, BookCopy, BookSeries
from categories.models import Category
from publishers.models import Publisher
from users.models import User

BASE = "/api/dashboard/"


def make_book(title, authors=(), categories=(), publisher=None, year=None, series=None, volume=None, addresses=()):
    book = Book.objects.create(title=title, publisher=publisher, publish_year=year, series=series, volume_number=volume)
    book.authors.set(authors)
    book.categories.set(categories)
    for address in addresses:
        BookCopy.objects.create(book=book, address=address)
    return book


class DashboardTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user("ali", "pass1234", name="علی")
        self.client.force_authenticate(self.user)

        self.a1 = Author.objects.create(name="الف")
        self.a2 = Author.objects.create(name="ب")
        Author.objects.create(name="بدون کتاب")
        self.cat = Category.objects.create(title="رمان")
        self.pub = Publisher.objects.create(name="نی")
        self.series = BookSeries.objects.create(title="دهخدا")

        make_book("کتاب ۱", [self.a1], [self.cat], self.pub, 1390, addresses=["01-01", "01-02", "02-05"])
        make_book("کتاب ۲", [self.a1, self.a2], [], None, 1395, addresses=["01-01"])
        make_book("دهخدا ۱", [self.a2], [], self.pub, None, self.series, 1, addresses=["03-10"])
        make_book("دهخدا ۲", [self.a2], [], self.pub, 1399, self.series, 2, addresses=[])

        BookCopy.objects.filter(address="03-10").update(is_loaned=True, loaned_to="رضا")
        BookCopy.objects.create(book=Book.objects.get(title="کتاب ۲"), address="خراب")

    def get(self, name, **params):
        res = self.client.get(BASE + name + "/", params)
        self.assertEqual(res.status_code, 200, res.data)
        return res.data["data"]

    def test_requires_login(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(BASE + "summary/").status_code, 401)

    def test_summary(self):
        data = self.get("summary")
        self.assertEqual(data["books"], 4)
        self.assertEqual(data["copies"], 6)
        self.assertEqual(data["authors"], 3)
        self.assertEqual(data["categories"], 1)
        self.assertEqual(data["series"], 1)
        self.assertEqual(data["publishers"], 1)
        self.assertEqual(data["loaned_copies"], 1)
        self.assertEqual(data["available_copies"], 5)

    def test_books_by_author_limit(self):
        data = self.get("books-by-author")
        self.assertEqual([(i["name"], i["count"]) for i in data["items"]], [("ب", 3), ("الف", 2)])
        self.assertEqual(data["total_items"], 2)  # نویسنده‌ی بدون کتاب نمی‌آید

        data = self.get("books-by-author", limit=1)
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["total_items"], 2)
        self.assertEqual(len(self.get("books-by-author", limit="all")["items"]), 2)
        self.assertEqual(len(self.get("books-by-author", limit="abc")["items"]), 2)  # نامعتبر → پیش‌فرض ۱۰

    def test_books_by_category_and_publisher(self):
        cats = self.get("books-by-category")
        self.assertEqual(cats["items"][0]["name"], "رمان")
        self.assertEqual(cats["items"][0]["count"], 1)

        pubs = self.get("books-by-publisher")
        self.assertEqual(pubs["items"][0]["count"], 3)
        self.assertEqual(pubs["books_without_publisher"], 1)

    def test_copies_by_book(self):
        items = self.get("copies-by-book")["items"]
        self.assertEqual(items[0]["name"], "کتاب ۱")
        self.assertEqual(items[0]["count"], 3)
        self.assertEqual(items[-1]["count"], 0)

    def test_copies_by_shelf_heatmap(self):
        data = self.get("copies-by-shelf")
        self.assertEqual({s["shelf"]: s["count"] for s in data["shelves"]}, {1: 3, 2: 1, 3: 1})
        self.assertEqual(data["invalid_address_copies"], 1)
        cells = {(c["shelf"], c["row"]): c["count"] for c in data["heatmap"]["cells"]}
        self.assertEqual(cells[(1, 1)], 2)
        self.assertEqual(data["heatmap"]["max_count"], 2)
        self.assertEqual(data["heatmap"]["max_shelf"], 3)
        self.assertEqual(data["heatmap"]["max_row"], 10)

    def test_books_by_year(self):
        data = self.get("books-by-year")
        self.assertEqual([(i["label"], i["count"]) for i in data["items"]], [("1390", 1), ("1395", 1), ("1399", 1)])
        self.assertEqual(data["unknown"], 1)

        data = self.get("books-by-year", bucket=10)
        self.assertEqual([(i["label"], i["count"]) for i in data["items"]], [("1390–1399", 3)])

    def test_series_overview(self):
        data = self.get("series")
        self.assertEqual(data["total_items"], 1)
        series = data["items"][0]
        self.assertEqual(series["title"], "دهخدا")
        self.assertEqual(series["books_count"], 2)
        self.assertEqual([b["volume_number"] for b in series["books"]], [1, 2])
        self.assertEqual(self.get("series", search="نیست")["items"], [])

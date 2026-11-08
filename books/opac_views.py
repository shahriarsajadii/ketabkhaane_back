import re
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from rest_framework.views import APIView

from core.responses import ResponseHelper

book_rh = ResponseHelper("کتاب", "کتاب‌ها")

OPAC_BASE = "https://opac.nlai.ir"
HEADERS = {"User-Agent": "Mozilla/5.0"}


# =====================================================
# ابزارهای کمکی
# =====================================================
def normalize_text(value):
    value = (
        value
        .replace("ي", "ی")
        .replace("ك", "ک")
        .replace("\u200f", "")
        .replace("\u200e", "")
        .replace("\u202a", "")
        .replace("\u202b", "")
        .replace("\u202c", "")
        .replace("\u202d", "")
        .replace("\u202e", "")
        .replace("\u200c", " ")
    )
    return re.sub(r"\s+", " ", value).strip()


def split_title_and_author(title_and_author, main_entry=""):
    """
    «عنوان و نام پدیدآور» در فهرست ملی معمولاً به شکل
        «عنوان [کتاب] : زیرعنوان / نام نویسنده ؛ ترجمه ...»
    است. عنوان و نویسنده را از آن جدا می‌کنیم.
    اگر نام پدیدآور نبود، از «سرشناسه» (مثل «کهریزه، ناصر، ۱۳۵۰-») استفاده می‌کنیم.
    """
    title, _, rest = (title_and_author or "").partition(" / ")

    # حذف نوع مدرک مثل [کتاب] یا [نوار]
    title = re.sub(r"\s*\[[^\]]*\]", "", title)
    title = title.strip(" :;./،؛")

    author = re.split(r"[؛;]", rest)[0].strip(" .،")

    if not author and main_entry:
        # «کهریزه، ناصر، ۱۳۵۰-»  →  «ناصر کهریزه»
        cleaned = re.sub(r"[\d۰-۹\-\s.]+$", "", main_entry).strip(" .،")
        parts = [p.strip() for p in cleaned.split("،") if p.strip()]
        author = " ".join(reversed(parts[:2])) if len(parts) >= 2 else cleaned

    return title, author


# =====================================================
# جستجو در کتابخانه ملی
# =====================================================
class SearchBookOpac(APIView):
    """
    POST /api/books/search_by_shabak/
        { "type": "shabak" | "title", "value": "..." }
    """

    def post(self, request):
        search_value = (request.data.get("value") or "").strip()
        search_type = request.data.get("type", "shabak")

        if not search_value:
            return book_rh.failed_response(message="وارد کردن عبارت جست‌وجو الزامی است.")

        search_fields = {
            "shabak": "221091",
            "title": "220885",
        }
        index_field_id = search_fields.get(search_type)
        if not index_field_id:
            return book_rh.failed_response(message="نوع جست‌وجو معتبر نیست.")

        url = f"{OPAC_BASE}/opac-prod/search/bibliographicSimpleSearchProcess.do"
        params = {
            "simpleSearch.value": search_value,
            "bibliographicLimitQueryBuilder.biblioDocType": "",
            "simpleSearch.indexFieldId": index_field_id,
            "nliHolding": "",
            "command": "I",
            "simpleSearch.tokenized": "true",
            "classType": "0",
            "pageStatus": "0",
            "bibliographicLimitQueryBuilder.useDateRange": "null",
            "bibliographicLimitQueryBuilder.year": "",
            "documentType": "",
            "attributes.locale": "fa",
        }

        try:
            response = requests.get(url, params=params, headers=HEADERS, timeout=20)
            response.raise_for_status()
        except requests.RequestException:
            return book_rh.failed_response(
                message="خطا در ارتباط با سامانه کتابخانه ملی",
                status_code=502,
            )

        soup = BeautifulSoup(response.text, "html.parser")

        books = []
        for row in soup.select("#table tr.gridrownormal3"):
            title = row.select_one('input[name$=".title"]')
            author = row.select_one('input[name$=".author"]')
            publish_date = row.select_one('input[name$=".publisherDate"]')
            detail_link = row.select_one('a[href*="briefListSearch.do"]')

            href = detail_link.get("href") if detail_link else None
            opac_id = parse_qs(urlparse(href).query).get("id", [None])[0] if href else None

            books.append({
                "title": title.get("value") if title else None,
                "author": author.get("value") if author else None,
                "opac_id": opac_id,
                "publish_date": publish_date.get("value") if publish_date else None,
                "detail_url": urljoin(OPAC_BASE, href) if href else None,
            })

        if not books:
            return book_rh.not_found_response(message="کتابی در کتابخانه ملی پیدا نشد.")

        return book_rh.success_get_all_response(data=books)


# =====================================================
# جزئیات یک کتاب
# =====================================================
class GetBookByOpacId(APIView):
    """
    POST /api/books/get_by_opac_id/    { "opac_book_id": "5104023" }

    خروجی data:
        title, author, publication, physical_description, isbn, cataloging_status,
        subjects, lcc, dewey, national_bibliography_number
    """

    FIELD_MAPPING = {
        "سرشناسه": "main_entry",
        "عنوان و نام پدیدآور": "title_and_author",
        "مشخصات نشر": "publication",
        "مشخصات ظاهری": "physical_description",
        "فروست": "series",
        "شابک": "isbn",
        "موضوع": "subjects",
        "شناسه افزوده": "additional_entry",
        "رده بندی کنگره": "lcc",
        "رده بندی دیویی": "dewey",
        "شماره کتابشناسی ملی": "national_bibliography_number",
        "عنوان به زبان دیگر": "other_title",
        "آوانویسی عنوان": "title_transliteration",
        "وضعیت فهرست نویسی": "cataloging_status",
    }

    OUTPUT_KEYS = (
        "publication", "physical_description", "isbn", "cataloging_status",
        "subjects", "lcc", "dewey", "national_bibliography_number",
    )

    def post(self, request):
        opac_book_id = request.data.get("opac_book_id")
        if not opac_book_id:
            return book_rh.failed_response(message="وارد کردن آیدی کتاب کتابخانه ملی الزامی است.")

        url = f"{OPAC_BASE}/opac-prod/search/briefListSearch.do"
        params = {
            "command": "FULL_VIEW",
            "id": opac_book_id,
            "pageStatus": 0,
            "sortKeyValue1": "sortkey_title",
            "sortKeyValue2": "sortkey_author",
        }

        try:
            response = requests.get(url, params=params, headers=HEADERS, timeout=20)
            response.raise_for_status()
        except requests.RequestException:
            return book_rh.failed_response(
                message="خطا در ارتباط با سامانه کتابخانه ملی",
                status_code=502,
            )

        soup = BeautifulSoup(response.text, "html.parser")
        mapping = {normalize_text(k): v for k, v in self.FIELD_MAPPING.items()}

        raw = {}
        for row in soup.find_all("tr"):
            columns = row.find_all("td", recursive=False)
            if len(columns) < 3:
                continue

            field_name = normalize_text(columns[0].get_text(separator=" ", strip=True))
            field_value = normalize_text(columns[2].get_text(separator=" ", strip=True))

            if not field_name or not field_value or "یادداشت" in field_name:
                continue

            key = mapping.get(field_name)
            if key:
                raw[key] = field_value

        if not raw:
            return book_rh.not_found_response(message="کتابی با این شناسه در کتابخانه ملی پیدا نشد.")

        title, author = split_title_and_author(
            raw.get("title_and_author", ""), raw.get("main_entry", "")
        )

        data = {"title": title, "author": author}
        for key in self.OUTPUT_KEYS:
            data[key] = raw.get(key, "")

        return book_rh.success_get_all_response(data=data)

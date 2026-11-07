"""
خواندن و نوشتن فایل اکسل کتاب‌ها (xlsx).

این ماژول عمداً به Django وابسته نیست: فقط فایل را به دیکشنری‌های آماده‌ی اعتبارسنجی تبدیل
می‌کند (parse_workbook) یا از دیکشنری‌ها فایل می‌سازد (build_template / build_export).
اعتبارسنجی نهایی و ذخیره در دیتابیس در books/services.py با همان سریالایزر API انجام می‌شود.

فرمت ستون‌ها (ردیف اول = عنوان ستون‌ها):

    نام کتاب | نویسنده | مترجم | تعداد | آدرس‌ها | ناشر | سال انتشار | شابک | دسته‌بندی‌ها | یادداشت

- نویسنده: یک یا چند نام، جداشده با ، یا | یا ؛ نویسنده‌های ناموجود خودکار ساخته می‌شوند.
- ناشر: یک نام؛ اگر ناموجود باشد خودکار ساخته می‌شود.
- آدرس‌ها: برای هر نسخه یک آدرس به شکل «قفسه-ردیف» مثل 01-05 (هرکدام ۱ تا ۵۰)،
  جداشده با | یا ؛ یا Alt+Enter (خط جدید).
  اگر تعداد > 1 و فقط یک آدرس نوشته شود، همان آدرس برای همه‌ی نسخه‌ها ثبت می‌شود.
- دسته‌بندی‌ها: جداشده با ، یا , یا | ؛ دسته‌بندی‌های ناموجود خودکار ساخته می‌شوند.
"""
import io
import re
from dataclasses import dataclass, field
from typing import Iterable

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# (کلید فیلد, عنوان ستون, عرض ستون)
COLUMNS = [
    ("title", "نام کتاب", 32),
    ("author", "نویسنده", 24),
    ("translator", "مترجم", 24),
    ("count", "تعداد", 9),
    ("addresses", "آدرس‌ها", 42),
    ("publisher", "ناشر", 22),
    ("publish_year", "سال انتشار", 12),
    ("isbn", "شابک", 18),
    ("categories", "دسته‌بندی‌ها", 28),
    ("note", "یادداشت", 40),
]
FIELD_LABELS = {key: label for key, label, _ in COLUMNS}
REQUIRED_FIELDS = ("title", "author", "translator", "addresses")

# نام‌های دیگری که برای هر ستون پذیرفته می‌شود (بعد از normalize_header)
_EXTRA_ALIASES = {
    "title": ["نام", "عنوان", "عنوان کتاب", "title", "name", "book"],
    "author": ["نویسنده", "مولف", "مؤلف", "author"],
    "translator": ["مترجم", "translator"],
    "count": ["تعداد", "تعداد نسخه", "count", "qty", "quantity"],
    "addresses": ["آدرس", "آدرس قفسه", "قفسه", "محل نگهداری", "address", "addresses", "location"],
    "publisher": ["ناشر", "انتشارات", "publisher"],
    "publish_year": ["سال", "سال نشر", "سال چاپ", "publish_year", "year"],
    "isbn": ["شابک", "isbn"],
    "categories": ["دسته", "دسته بندی", "دسته‌بندی", "دسته‌ها", "categories", "category"],
    "note": ["یادداشت", "یادداشت‌ها", "توضیحات", "note", "notes"],
}

_CHAR_MAP = str.maketrans({
    "ي": "ی", "ى": "ی", "ك": "ک",      # حروف عربی → فارسی
    "\u200f": None, "\u200e": None,     # RLM / LRM
    "\ufeff": None,                     # BOM
})
_DIGIT_MAP = {
    **{0x06F0 + i: ord("0") + i for i in range(10)},   # ۰-۹
    **{0x0660 + i: ord("0") + i for i in range(10)},   # ٠-٩
}
_ADDRESS_SPLIT = re.compile(r"[|\n\r;؛]+")
_CATEGORY_SPLIT = re.compile(r"[|\n\r;؛,،]+")
# نام نویسنده ممکن است «Last, First» لاتین باشد؛ پس کاما‌ی لاتین جداکننده نیست
_AUTHOR_SPLIT = re.compile(r"[|\n\r;؛،]+")


class ExcelImportError(Exception):
    """خطای ساختاری فایل (فایل خراب، ستون ضروری نیست، ردیف زیاد، ...)"""


@dataclass
class ParsedRow:
    number: int                      # شماره‌ی ردیف در اکسل (ردیف عنوان = 1)
    payload: dict                    # آماده‌ی BookCreateUpdateSerializer (بدون categories/authors/publisher)
    category_names: list = field(default_factory=list)
    author_names: list = field(default_factory=list)
    publisher_name: str = ""


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def fix_chars(text: str) -> str:
    return text.translate(_CHAR_MAP)


def to_ascii_digits(text: str) -> str:
    return text.translate(_DIGIT_MAP)


def normalize_header(value) -> str:
    text = fix_chars(str(value)).lower()
    for ch in ("\u200c", " ", "\u00a0", "_", "-", ":"):
        text = text.replace(ch, "")
    return text


def _build_header_map():
    mapping = {}
    for key, label, _ in COLUMNS:
        mapping[normalize_header(label)] = key
        mapping[normalize_header(key)] = key
    for key, aliases in _EXTRA_ALIASES.items():
        for alias in aliases:
            mapping.setdefault(normalize_header(alias), key)
    return mapping


HEADER_TO_FIELD = _build_header_map()


def split_values(text: str, pattern, unique: bool = False) -> list:
    items = [part.strip() for part in pattern.split(text or "")]
    items = [item for item in items if item]
    if not unique:
        return items
    seen, result = set(), []
    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _clean_cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return fix_chars(str(value)).strip()


def _row_to_payload(number: int, raw: dict, max_copies: int) -> ParsedRow:
    payload = {}

    for key in ("title", "translator", "isbn", "note"):
        if raw.get(key):
            payload[key] = raw[key]

    for key in ("count", "publish_year"):
        text = to_ascii_digits(raw.get(key, ""))
        if text:
            # اگر عدد نبود همان متن می‌رود تا سریالایزر پیام خطای مناسب بدهد
            payload[key] = int(text) if text.isdigit() else text

    addresses = split_values(raw.get("addresses", ""), _ADDRESS_SPLIT)
    count = payload.get("count")
    if isinstance(count, int) and 1 < count <= max_copies and len(addresses) == 1:
        addresses = addresses * count
    payload["addresses"] = addresses

    category_names = split_values(raw.get("categories", ""), _CATEGORY_SPLIT, unique=True)
    author_names = split_values(raw.get("author", ""), _AUTHOR_SPLIT, unique=True)
    publisher_name = " ".join(raw.get("publisher", "").split())
    return ParsedRow(
        number=number,
        payload=payload,
        category_names=category_names,
        author_names=author_names,
        publisher_name=publisher_name,
    )


# ------------------------------------------------------------------
# Import
# ------------------------------------------------------------------
def parse_workbook(content: bytes, max_rows: int = 2000, max_copies: int = 500) -> list:
    """
    اولین شیت فایل را می‌خواند و لیستی از ParsedRow برمی‌گرداند.
    ردیف‌های کاملاً خالی نادیده گرفته می‌شوند.
    """
    try:
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception:
        raise ExcelImportError("فایل اکسل معتبر نیست. لطفاً یک فایل .xlsx آپلود کنید.")

    try:
        if not workbook.worksheets:
            raise ExcelImportError("فایل هیچ شیتی ندارد.")

        rows = workbook.worksheets[0].iter_rows(values_only=True)
        header = next(rows, None)
        if not header:
            raise ExcelImportError("فایل خالی است.")

        column_map = {}  # ایندکس ستون → نام فیلد
        for index, cell in enumerate(header):
            if cell is None:
                continue
            key = HEADER_TO_FIELD.get(normalize_header(cell))
            if key and key not in column_map.values():
                column_map[index] = key

        missing = [FIELD_LABELS[k] for k in REQUIRED_FIELDS if k not in column_map.values()]
        if missing:
            raise ExcelImportError(
                "ستون‌های ضروری در ردیف اول فایل پیدا نشد: " + "، ".join(missing)
                + ". بهتر است از فایل نمونه‌ی سیستم استفاده کنید."
            )

        parsed = []
        for number, row in enumerate(rows, start=2):
            raw = {
                key: _clean_cell(row[index]) if index < len(row) else ""
                for index, key in column_map.items()
            }
            if not any(raw.values()):
                continue
            if len(parsed) >= max_rows:
                raise ExcelImportError(
                    f"تعداد ردیف‌ها بیشتر از {max_rows} است. فایل را به چند بخش تقسیم کنید."
                )
            parsed.append(_row_to_payload(number, raw, max_copies))

        if not parsed:
            raise ExcelImportError("هیچ ردیف داده‌ای در فایل پیدا نشد.")
        return parsed
    finally:
        workbook.close()


# ------------------------------------------------------------------
# Export / Template
# ------------------------------------------------------------------
_HEADER_FONT = Font(bold=True, color="FFFFFF")
_HEADER_FILL = PatternFill("solid", fgColor="2F5D50")
_WRAP = Alignment(wrap_text=True, vertical="top", horizontal="right")


def _set_cell(ws, row: int, col: int, value):
    cell = ws.cell(row=row, column=col)
    cell.value = value
    if isinstance(value, str):
        # openpyxl هر متنی که با = شروع شود را «فرمول» می‌گیرد؛ اجباراً متن می‌کنیم
        # تا عنوان‌های عجیب (مثلا =HYPERLINK(...)) هنگام باز کردن در اکسل اجرا نشوند.
        cell.data_type = "s"
    return cell


def _prepare_sheet(ws):
    ws.sheet_view.rightToLeft = True
    for col, (_, label, width) in enumerate(COLUMNS, start=1):
        cell = _set_cell(ws, 1, col, label)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.column_dimensions[get_column_letter(col)].width = width
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(COLUMNS))}1"


def _to_bytes(workbook) -> bytes:
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def build_template() -> bytes:
    """فایل نمونه: شیت خالی با عنوان ستون‌ها + شیت راهنما"""
    wb = Workbook()
    ws = wb.active
    ws.title = "کتاب‌ها"
    _prepare_sheet(ws)

    guide = wb.create_sheet("راهنما")
    guide.sheet_view.rightToLeft = True
    guide.column_dimensions["A"].width = 110
    lines = [
        "راهنمای فایل ورود دسته‌جمعی کتاب‌ها",
        "",
        "۱) اطلاعات را در شیت «کتاب‌ها» و از ردیف دوم به بعد وارد کنید. ردیف اول (عنوان ستون‌ها) را تغییر ندهید.",
        "۲) ستون‌های اجباری: نام کتاب، نویسنده، مترجم، آدرس‌ها.",
        "۳) تعداد: اختیاری است. اگر خالی باشد، برابر تعداد آدرس‌ها در نظر گرفته می‌شود.",
        "۴) آدرس‌ها: برای هر نسخه یک آدرس به شکل «قفسه-ردیف» بنویسید؛ هر دو عدد بین ۱ تا ۵۰ و با | یا ؛ از هم جدا شوند (یا داخل سلول Alt+Enter بزنید).",
        "    مثال: 01-05 | 01-06 | 12-30   ← سه نسخه؛ اولی قفسه ۰۱ ردیف ۰۵، دومی قفسه ۰۱ ردیف ۰۶، سومی قفسه ۱۲ ردیف ۳۰",
        "    اگر تعداد ۳ باشد و فقط یک آدرس بنویسید، همان آدرس برای هر سه نسخه ثبت می‌شود.",
        "۵) نویسنده: اگر کتاب چند نویسنده دارد، نام‌ها را با ، یا | جدا کنید. ناشر: فقط یک نام. نویسنده/ناشر جدید خودکار ساخته می‌شود.",
        "۶) دسته‌بندی‌ها: چند دسته را با ، یا | جدا کنید. دسته‌های جدید خودکار ساخته می‌شوند.",
        "۷) اگر کتابی با همین نام، نویسنده‌ها، مترجم و ناشر قبلاً ثبت شده باشد، آن ردیف خطا می‌دهد",
        "    (برای کتاب تکراری، تعداد و آدرس‌های همان کتاب را ویرایش کنید).",
        "۸) عکس کتاب‌ها از این طریق ثبت نمی‌شود؛ بعداً از صفحه‌ی خود کتاب آپلود کنید.",
    ]
    for row, text in enumerate(lines, start=1):
        cell = _set_cell(guide, row, 1, text)
        cell.alignment = Alignment(horizontal="right", wrap_text=True)
    guide["A1"].font = Font(bold=True, size=13)

    return _to_bytes(wb)


def build_export(rows: Iterable[dict]) -> bytes:
    """
    rows: دیکشنری‌هایی با کلیدهای COLUMNS.
    (count و publish_year عدد؛ بقیه متن)
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "کتاب‌ها"
    _prepare_sheet(ws)

    for row_number, row in enumerate(rows, start=2):
        for col, (key, _, _) in enumerate(COLUMNS, start=1):
            value = row.get(key)
            if value is None or value == "":
                continue
            cell = _set_cell(ws, row_number, col, value)
            if key in ("addresses", "note", "categories", "title"):
                cell.alignment = _WRAP

    return _to_bytes(wb)

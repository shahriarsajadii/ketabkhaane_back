"""
تست ماژول اکسل (بدون نیاز به Django):
    python -m unittest books.tests.test_excel
"""
import io
import unittest

from openpyxl import Workbook, load_workbook

from books import excel


def make_xlsx(header, rows):
    wb = Workbook()
    ws = wb.active
    if header is not None:
        ws.append(header)
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


HEADER = ["نام کتاب", "نویسنده", "مترجم", "تعداد", "آدرس‌ها", "ناشر", "سال انتشار", "شابک", "دسته‌بندی‌ها", "یادداشت"]


class ParseTests(unittest.TestCase):
    def test_basic_row(self):
        content = make_xlsx(HEADER, [
            ["یادداشت‌های زیرزمینی", "داستایفسکی", "مترجم", 3, "01-02 | 01-03 | 01-04", "نشر", 1398, "", "رمان، کلاسیک", "خوب بود"],
        ])
        rows = excel.parse_workbook(content)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row.number, 2)
        self.assertEqual(row.payload["count"], 3)
        self.assertEqual(row.payload["addresses"], ["01-02", "01-03", "01-04"])
        self.assertEqual(row.author_names, ["داستایفسکی"])
        self.assertEqual(row.publisher_name, "نشر")
        self.assertNotIn("author", row.payload)
        self.assertNotIn("publisher", row.payload)
        self.assertEqual(row.payload["publish_year"], 1398)
        self.assertEqual(row.category_names, ["رمان", "کلاسیک"])
        self.assertEqual(row.payload["note"], "خوب بود")
        self.assertNotIn("isbn", row.payload)

    def test_single_address_replicated_by_count(self):
        content = make_xlsx(HEADER, [["الف", "ب", "ج", 3, "01-01", None, None, None, None, None]])
        row = excel.parse_workbook(content)[0]
        self.assertEqual(row.payload["addresses"], ["01-01"] * 3)

    def test_count_omitted(self):
        content = make_xlsx(HEADER, [["الف", "ب", "ج", None, "01-01\n01-02", None, None, None, None, None]])
        row = excel.parse_workbook(content)[0]
        self.assertNotIn("count", row.payload)
        self.assertEqual(row.payload["addresses"], ["01-01", "01-02"])

    def test_persian_digits_and_float_cells(self):
        content = make_xlsx(HEADER, [["الف", "ب", "ج", "۲", "x | y", None, "۱۳۹۸", None, None, None]])
        row = excel.parse_workbook(content)[0]
        self.assertEqual(row.payload["count"], 2)
        self.assertEqual(row.payload["publish_year"], 1398)
        content = make_xlsx(HEADER, [["الف", "ب", "ج", 2.0, "x | y", None, 1398.0, None, None, None]])
        row = excel.parse_workbook(content)[0]
        self.assertEqual(row.payload["count"], 2)
        self.assertEqual(row.payload["publish_year"], 1398)

    def test_invalid_number_is_kept_as_text_for_serializer_error(self):
        content = make_xlsx(HEADER, [["الف", "ب", "ج", "سه تا", "x", None, None, None, None, None]])
        self.assertEqual(excel.parse_workbook(content)[0].payload["count"], "سه تا")

    def test_header_variants_and_arabic_letters(self):
        header = ["عنوان", "نويسنده", "مترجم", "آدرس قفسه"]          # ي عربی
        content = make_xlsx(header, [["ك", "ب", "ج", "قفسه ۱"]])      # ك عربی
        row = excel.parse_workbook(content)[0]
        self.assertEqual(row.payload["title"], "ک")
        self.assertEqual(row.author_names, ["ب"])
        self.assertEqual(row.payload["addresses"], ["قفسه ۱"])

    def test_english_headers(self):
        content = make_xlsx(["title", "author", "translator", "address"], [["A", "B", "C", "S1"]])
        self.assertEqual(excel.parse_workbook(content)[0].payload["title"], "A")

    def test_blank_rows_skipped_and_row_numbers(self):
        content = make_xlsx(HEADER, [
            ["الف", "ب", "ج", 1, "x", None, None, None, None, None],
            [None] * 10,
            ["د", "ه", "و", 1, "y", None, None, None, None, None],
        ])
        rows = excel.parse_workbook(content)
        self.assertEqual([r.number for r in rows], [2, 4])

    def test_missing_required_column(self):
        content = make_xlsx(["نام کتاب", "نویسنده"], [["الف", "ب"]])
        with self.assertRaises(excel.ExcelImportError) as ctx:
            excel.parse_workbook(content)
        self.assertIn("مترجم", str(ctx.exception))
        self.assertIn("آدرس‌ها", str(ctx.exception))

    def test_garbage_file(self):
        with self.assertRaises(excel.ExcelImportError):
            excel.parse_workbook(b"this is not an excel file")

    def test_no_data_rows(self):
        with self.assertRaises(excel.ExcelImportError):
            excel.parse_workbook(make_xlsx(HEADER, []))

    def test_too_many_rows(self):
        content = make_xlsx(HEADER, [["الف", "ب", "ج", 1, "x", None, None, None, None, None]] * 5)
        with self.assertRaises(excel.ExcelImportError):
            excel.parse_workbook(content, max_rows=3)

    def test_duplicate_category_names_deduped(self):
        content = make_xlsx(HEADER, [["الف", "ب", "ج", 1, "x", None, None, None, "رمان، رمان | شعر", None]])
        self.assertEqual(excel.parse_workbook(content)[0].category_names, ["رمان", "شعر"])


    def test_multiple_authors_split_and_deduped(self):
        content = make_xlsx(HEADER, [[
            "الف", "علی | رضا، علی ; Smith, John", "ج", 1, "01-01", None, None, None, None, None,
        ]])
        # کاما‌ی لاتین جداکننده نیست (Last, First)
        self.assertEqual(excel.parse_workbook(content)[0].author_names, ["علی", "رضا", "Smith, John"])

    def test_publisher_whitespace_is_collapsed(self):
        content = make_xlsx(HEADER, [["الف", "ب", "ج", 1, "01-01", "  نشر   نی ", None, None, None, None]])
        self.assertEqual(excel.parse_workbook(content)[0].publisher_name, "نشر نی")


class BuildTests(unittest.TestCase):
    def test_template_is_parseable_structure(self):
        wb = load_workbook(io.BytesIO(excel.build_template()))
        self.assertEqual(wb.sheetnames, ["کتاب‌ها", "راهنما"])
        header = [c.value for c in wb["کتاب‌ها"][1]]
        self.assertEqual(header, [label for _, label, _ in excel.COLUMNS])
        # فایل خالی نمونه باید «بدون ردیف داده» خطا بدهد، نه اینکه ردیف نمونه وارد شود
        with self.assertRaises(excel.ExcelImportError):
            excel.parse_workbook(excel.build_template())

    def test_export_roundtrip(self):
        rows = [{
            "title": "یادداشت‌های زیرزمینی", "author": "الف", "translator": "ب", "count": 3,
            "addresses": "01-01 | 01-02 | 01-03", "publisher": "", "publish_year": 1398,
            "isbn": "978-1", "categories": "رمان، کلاسیک", "note": "یادداشت",
        }]
        content = excel.build_export(rows)
        parsed = excel.parse_workbook(content)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0].payload["title"], "یادداشت‌های زیرزمینی")
        self.assertEqual(parsed[0].payload["count"], 3)
        self.assertEqual(parsed[0].payload["addresses"], ["01-01", "01-02", "01-03"])
        self.assertEqual(parsed[0].author_names, ["الف"])
        self.assertEqual(parsed[0].category_names, ["رمان", "کلاسیک"])

    def test_formula_injection_is_neutralised(self):
        rows = [{"title": "=1+1", "author": "@SUM(A1)", "translator": "-2+3", "count": 1, "addresses": "x"}]
        content = excel.build_export(rows)
        wb = load_workbook(io.BytesIO(content))
        cell = wb.active["A2"]
        self.assertEqual(cell.data_type, "s")
        self.assertEqual(cell.value, "=1+1")
        # در رفت‌وبرگشت هم به‌صورت متن خوانده می‌شود
        self.assertEqual(excel.parse_workbook(content)[0].payload["title"], "=1+1")


if __name__ == "__main__":
    unittest.main()

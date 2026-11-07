"""
تست ماژول آدرس (بدون نیاز به Django):
    python -m unittest books.tests.test_addresses
"""
import unittest

from books.addresses import normalize_address


class NormalizeAddressTests(unittest.TestCase):
    def test_canonical_form_is_kept(self):
        self.assertEqual(normalize_address("01-05"), "01-05")
        self.assertEqual(normalize_address("50-50"), "50-50")

    def test_pads_and_trims(self):
        self.assertEqual(normalize_address("1-5"), "01-05")
        self.assertEqual(normalize_address("  1 - 5 "), "01-05")

    def test_persian_and_arabic_digits(self):
        self.assertEqual(normalize_address("۰۱-۰۵"), "01-05")
        self.assertEqual(normalize_address("٠٢-١٠"), "02-10")

    def test_unicode_dashes(self):
        self.assertEqual(normalize_address("01\u201305"), "01-05")

    def test_out_of_range(self):
        for bad in ("00-05", "01-00", "51-01", "01-51"):
            with self.assertRaises(ValueError, msg=bad):
                normalize_address(bad)

    def test_custom_limits(self):
        self.assertEqual(normalize_address("10-20", shelf_max=10, row_max=20), "10-20")
        with self.assertRaises(ValueError):
            normalize_address("11-20", shelf_max=10, row_max=20)

    def test_bad_format(self):
        for bad in ("", "قفسه ۲", "01", "01-", "-05", "1-2-3", "001-05", "01-005", "a-b", None):
            with self.assertRaises(ValueError, msg=repr(bad)):
                normalize_address(bad)


if __name__ == "__main__":
    unittest.main()

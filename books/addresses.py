import re

_DIGIT_MAP = {
    **{0x06F0 + i: ord("0") + i for i in range(10)},   # ۰-۹
    **{0x0660 + i: ord("0") + i for i in range(10)},   # ٠-٩
}
_ADDRESS_RE = re.compile(r"^(\d{1,2})\s*[-\u2010\u2011\u2012\u2013\u2014\u2212]\s*(\d{1,2})$")

ADDRESS_EXAMPLE = "01-05"


def format_address(shelf: int, row: int) -> str:
    return f"{shelf:02d}-{row:02d}"


def normalize_address(value, shelf_max: int = 50, row_max: int = 50) -> str:
    text = str(value or "").strip().translate(_DIGIT_MAP)
    match = _ADDRESS_RE.match(text)
    if not match:
        raise ValueError(
            f"آدرس باید به شکل «قفسه-ردیف» باشد، مثلاً {ADDRESS_EXAMPLE} (قفسه ۰۱، ردیف ۰۵)."
        )
    shelf, row = int(match.group(1)), int(match.group(2))
    if not 1 <= shelf <= shelf_max:
        raise ValueError(f"شماره‌ی قفسه باید بین ۱ تا {shelf_max} باشد.")
    if not 1 <= row <= row_max:
        raise ValueError(f"شماره‌ی ردیف باید بین ۱ تا {row_max} باشد.")
    return format_address(shelf, row)

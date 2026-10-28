import re

_DIGITS = re.compile(r"\D")


def normalize_phone(value: str) -> str:
    """Normalise an Indian mobile number to WhatsApp format: 91 + 10 digits.

    Accepts '9876543210', '+91 98765 43210', '09876543210', '919876543210'.
    """
    digits = _DIGITS.sub("", value or "")
    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if len(digits) == 10:
        digits = "91" + digits
    if not (len(digits) == 12 and digits.startswith("91") and digits[2] in "6789"):
        raise ValueError("Enter a valid 10-digit Indian mobile number")
    return digits


def display_phone(value: str) -> str:
    """'919876543210' -> '98765 43210'"""
    local = value[2:] if value.startswith("91") and len(value) == 12 else value
    return f"{local[:5]} {local[5:]}" if len(local) == 10 else local

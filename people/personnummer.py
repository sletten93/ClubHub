import re
from datetime import date

from django.core.exceptions import ValidationError

_PATTERN = re.compile(r"^(?:(\d{2}))?(\d{6})[-+]?(\d{4})$")


def _luhn(ten_digits):
    total = 0
    for index, char in enumerate(reversed(ten_digits)):
        digit = int(char)
        if index % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def normalize_personnummer(value):
    cleaned = re.sub(r"\s", "", str(value))
    match = _PATTERN.match(cleaned)
    if match is None:
        raise ValidationError("Invalid personnummer.")
    century, yymmdd, tail = match.groups()
    if not _luhn(yymmdd + tail):
        raise ValidationError("Invalid personnummer (checksum).")
    month = int(yymmdd[2:4])
    day = int(yymmdd[4:6])
    if not 1 <= month <= 12:
        raise ValidationError("Invalid personnummer.")
    real_day = day - 60 if day > 60 else day
    if not 1 <= real_day <= 31:
        raise ValidationError("Invalid personnummer.")
    today = date.today()
    if century is not None:
        prefix = century
    else:
        short_year = int(yymmdd[:2])
        prefix = "20" if 2000 + short_year <= today.year else "19"
    try:
        date(int(prefix + yymmdd[:2]), month, real_day)
    except ValueError:
        raise ValidationError("Invalid personnummer.")
    return prefix + yymmdd + tail


def birth_date_from_personnummer(value):
    try:
        normalized = normalize_personnummer(value)
    except ValidationError:
        return None
    year = int(normalized[:4])
    month = int(normalized[4:6])
    day = int(normalized[6:8])
    if day > 60:
        day -= 60
    try:
        return date(year, month, day)
    except ValueError:
        return None

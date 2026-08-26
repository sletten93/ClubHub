import re
from datetime import date

from django.core.exceptions import ValidationError

# Full personnummer: optional 2-digit century + YYMMDD + 4-digit tail.
_FULL_PATTERN = re.compile(r"^(?:(\d{2}))?(\d{6})[-+]?(\d{4})$")
# Masked/partial: same date part but the tail is missing or replaced by ****.
# Sportadmin exports mask the last four digits, and some members have no tail
# stored at all, so both forms must be accepted.
_MASKED_PATTERN = re.compile(r"^(?:(\d{2}))?(\d{6})[-+]?(?:\*{4})?$")


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


def _century_prefix(century, yymmdd):
    today = date.today()
    if century is not None:
        return century
    short_year = int(yymmdd[:2])
    return "20" if 2000 + short_year <= today.year else "19"


def _validate_date_part(prefix, yymmdd):
    month = int(yymmdd[2:4])
    day = int(yymmdd[4:6])
    if not 1 <= month <= 12:
        raise ValidationError("Invalid personnummer.")
    real_day = day - 60 if day > 60 else day
    if not 1 <= real_day <= 31:
        raise ValidationError("Invalid personnummer.")
    try:
        date(int(prefix + yymmdd[:2]), month, real_day)
    except ValueError:
        raise ValidationError("Invalid personnummer.")


def normalize_personnummer(value):
    """Normalize to ``YYYYMMDDXXXX`` (full) or ``YYYYMMDD****`` (masked).

    An empty value normalizes to an empty string; callers decide whether that
    means NULL. Masked values cannot be checksum-verified, but the date part
    is still validated so birth dates stay trustworthy.
    """
    cleaned = re.sub(r"\s", "", str(value))
    if not cleaned:
        return ""
    match = _FULL_PATTERN.match(cleaned)
    if match is not None:
        century, yymmdd, tail = match.groups()
        if not _luhn(yymmdd + tail):
            raise ValidationError("Invalid personnummer (checksum).")
        prefix = _century_prefix(century, yymmdd)
        _validate_date_part(prefix, yymmdd)
        return prefix + yymmdd + tail
    match = _MASKED_PATTERN.match(cleaned)
    if match is not None:
        century, yymmdd = match.groups()
        prefix = _century_prefix(century, yymmdd)
        _validate_date_part(prefix, yymmdd)
        return prefix + yymmdd + "****"
    raise ValidationError("Invalid personnummer.")


def birth_date_from_personnummer(value):
    if not value:
        return None
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
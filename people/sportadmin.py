"""Import of Sportadmin "Personregister" Excel exports.

The export is one sheet with a header row. Column names repeat ("E-post",
"Telefon", "Relation" appear both at top level and inside the two guardian
blocks), so columns are resolved positionally while walking the header list.

Guardians ("Målsman 1/2") are denormalized strings, not person rows. They are
imported as Person rows without personnummer, matched on email (when present)
or exact full name, and linked through GuardianRelation with the free-form
relation text kept verbatim.
"""

import re
from datetime import date, datetime

from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator

from clubs.translations import translate

from .models import GuardianRelation, Membership, Person
from .personnummer import normalize_personnummer

AREA = "Personregister"

# Column name -> role. Roles marked with a suffix belong to the guardian
# blocks that follow each "Målsman N" column.
_COLUMN_ROLES = [
    ("Personnummer", "personnummer"),
    ("Kön", "gender"),
    ("Förnamn", "first_name"),
    ("Efternamn", "last_name"),
    ("c/o", None),
    ("Adress", "street_address"),
    ("Postnummer", "postal_code"),
    ("Stad", "city"),
    ("Land", None),
    ("Mobiltelefon", "phone_mobile"),
    ("Telefon hem", None),
    ("Telefon jobb", None),
    ("E-post", "email"),
    ("Målsman 1", "guardian"),
    ("Relation", "guardian_relation"),
    ("E-post", "guardian_email"),
    ("Telefon", "guardian_phone"),
    ("Målsman 2", "guardian"),
    ("Relation", "guardian_relation"),
    ("E-post", "guardian_email"),
    ("Telefon", "guardian_phone"),
    ("Skapad", None),
    ("Uppdaterad", None),
    ("Grupprekommendation", None),
    ("Övrigt", "notes"),
    ("MedlemsNr", None),
    ("StartÅr", "start_date"),
    ("Allergi", "allergy"),
]

_GENDER_MAP = {"man": Person.Gender.MALE, "kvinna": Person.Gender.FEMALE}

_email_validator = EmailValidator()
_whitespace = re.compile(r"\s+")


def _clean(value):
    if value is None:
        return ""
    return _whitespace.sub(" ", str(value)).strip()


def _parse_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = _clean(value)
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    return None


def _valid_email(value):
    text = _clean(value)
    if not text:
        return ""
    try:
        _email_validator(text)
    except ValidationError:
        return ""
    return text


def parse_sportadmin_personregister(data):
    """Parse an xlsx byte stream into ``(rows, warnings)``.

    Each row is a JSON-serializable dict with the Person fields plus a
    ``guardians`` list of ``{name, relation, email, phone}`` dicts. Rows that
    cannot be fully mapped still come through (with empty fields); problems
    are reported per row in ``warnings`` as translated strings.
    """
    import io

    import openpyxl

    workbook = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    sheet = workbook.active
    excel_rows = sheet.iter_rows(values_only=True)
    try:
        header = next(excel_rows)
    except StopIteration:
        return [], []

    # Resolve roles positionally: walk the header and consume expected columns
    # in order. Column names repeat ("E-post", "Relation", ...), so a pure
    # name lookup would collapse them; consuming sequentially keeps each
    # occurrence distinct. Unknown headers are ignored so future export
    # variants degrade gracefully.
    roles = []
    cursor = 0
    for cell in header:
        name = _clean(cell)
        role = None
        for offset in range(cursor, len(_COLUMN_ROLES)):
            known, mapped = _COLUMN_ROLES[offset]
            if name == known:
                role = mapped
                cursor = offset + 1
                break
        roles.append(role)

    def value_of(row, role):
        for index, candidate in enumerate(roles):
            if candidate == role:
                return row[index]
        return None

    rows, warnings = [], []
    for line_number, row in enumerate(excel_rows, start=2):
        if row is None or not any(_clean(cell) for cell in row):
            continue
        first_name = _clean(value_of(row, "first_name"))
        last_name = _clean(value_of(row, "last_name"))
        if not first_name and not last_name:
            continue

        row_warnings = []
        raw_pnr = _clean(value_of(row, "personnummer")).replace(" ", "")
        personnummer = None
        if raw_pnr:
            try:
                personnummer = normalize_personnummer(raw_pnr)
            except ValidationError:
                row_warnings.append(translate("Ogiltigt personnummer hoppas över.", AREA))

        email = _valid_email(value_of(row, "email"))
        if _clean(value_of(row, "email")) and not email:
            row_warnings.append(translate("Ogiltig e-postadress hoppas över.", AREA))

        gender_text = _clean(value_of(row, "gender")).lower()
        gender = _GENDER_MAP.get(gender_text, "")

        guardians = []
        current = None
        for index, role in enumerate(roles):
            if role == "guardian":
                name = _clean(row[index] if index < len(row) else None)
                if name:
                    current = {"name": name, "relation": "", "email": "", "phone": ""}
                    guardians.append(current)
                else:
                    current = None
            elif current is not None and role in ("guardian_relation", "guardian_email", "guardian_phone"):
                field = role.split("_", 1)[1]
                current[field] = _clean(row[index] if index < len(row) else None)

        rows.append(
            {
                "first_name": first_name,
                "last_name": last_name,
                "personnummer": personnummer,
                "gender": gender,
                "street_address": _clean(value_of(row, "street_address")),
                "postal_code": _clean(value_of(row, "postal_code")),
                "city": _clean(value_of(row, "city")),
                "email": email,
                "phone_mobile": _clean(value_of(row, "phone_mobile")),
                "notes": _clean(value_of(row, "notes")),
                "allergy": _clean(value_of(row, "allergy")),
                "start_date": (_parse_date(value_of(row, "start_date")) or "").isoformat()
                if _parse_date(value_of(row, "start_date"))
                else "",
                "guardians": guardians,
                "warnings": row_warnings,
            }
        )
        for warning in row_warnings:
            warnings.append(f"{first_name} {last_name} (rad {line_number}): {warning}")

    return rows, warnings


def _find_existing(club, data):
    """Match an imported row against an already registered person."""
    queryset = Person.objects.filter(club=club)
    pnr = data.get("personnummer")
    if pnr:
        return queryset.filter(personnummer=pnr).first()
    name_match = queryset.filter(
        first_name=data["first_name"], last_name=data["last_name"]
    )
    if data["email"]:
        return name_match.filter(email=data["email"]).first()
    return name_match.filter(email="").first()


def import_person_rows(club, rows):
    """Create Person/GuardianRelation/Membership records from parsed rows.

    Returns ``(created, skipped)`` counts. Rows matching an existing person
    (full/masked personnummer, or name+email for pnr-less rows) are skipped,
    making re-imports safe.
    """
    created = skipped = 0
    for data in rows:
        raw_pnr = data.get("personnummer")
        if raw_pnr:
            try:
                data["personnummer"] = normalize_personnummer(raw_pnr)
            except ValidationError:
                data["personnummer"] = None
        existing = _find_existing(club, data)
        if existing is not None:
            skipped += 1
            continue

        person = Person.objects.create(
            club=club,
            first_name=data["first_name"],
            last_name=data["last_name"],
            personnummer=data.get("personnummer") or None,
            gender=data.get("gender") or "",
            street_address=data.get("street_address", ""),
            postal_code=data.get("postal_code", ""),
            city=data.get("city", ""),
            email=data.get("email", ""),
            phone_mobile=data.get("phone_mobile", ""),
            notes=data.get("notes", ""),
            allergy=data.get("allergy", ""),
        )

        for guardian_data in data.get("guardians", []):
            name_parts = guardian_data["name"].split(" ", 1)
            guardian_first = name_parts[0]
            guardian_last = name_parts[1] if len(name_parts) > 1 else ""
            guardian_email = _valid_email(guardian_data.get("email", ""))
            guardian = None
            if guardian_email:
                guardian = Person.objects.filter(
                    club=club, email=guardian_email
                ).first()
            if guardian is None:
                guardian_query = Person.objects.filter(
                    club=club,
                    first_name=guardian_first,
                    last_name=guardian_last,
                )
                if guardian_email:
                    guardian = guardian_query.filter(email="").first()
                else:
                    guardian = (
                        guardian_query.filter(personnummer__isnull=True).first()
                        or guardian_query.first()
                    )
            if guardian is None:
                guardian = Person.objects.create(
                    club=club,
                    first_name=guardian_first,
                    last_name=guardian_last,
                    email=guardian_email,
                    phone_mobile=_clean(guardian_data.get("phone", "")),
                )
            elif guardian_email and not guardian.email:
                guardian.email = guardian_email
                guardian.save()
            GuardianRelation.objects.get_or_create(
                guardian=guardian,
                child=person,
                defaults={"relation": _clean(guardian_data.get("relation", ""))},
            )

        start_date = data.get("start_date")
        if start_date:
            Membership.objects.get_or_create(
                person=person,
                defaults={"status": Membership.Status.ACTIVE, "start_date": start_date},
            )
        created += 1
    return created, skipped
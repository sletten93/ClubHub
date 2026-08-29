"""Import of Sportadmin and ClubHub "Personregister" exports.

Two xlsx layouts are accepted:

* The Sportadmin export: one sheet with a header row whose column names
  repeat ("E-post", "Telefon", "Relation" appear both at top level and
  inside the two guardian blocks), resolved positionally while walking the
  header list.
* The ClubHub export (see people.views.PersonExportView): the same sheet
  with unique Swedish headers plus extra columns ("Roll",
  "Betalningsstatus", "Målsman", "Vårdnadshavare till") resolved by name.

The ClubHub XML export is accepted as well, mapped through the same
column set by tag name.

Guardians are denormalized strings, not person rows. They are imported as
Person rows without personnummer, matched on email (when present) or
exact full name, and linked through GuardianRelation with the free-form
relation text kept verbatim.
"""

import re
import xml.etree.ElementTree as ET
from datetime import date, datetime

from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator

from clubs.translations import translate

from .models import GuardianRelation, Membership, Person, StaffProfile
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

_GENDER_MAP = {
    "man": Person.Gender.MALE,
    "kvinna": Person.Gender.FEMALE,
    "icke-binär": Person.Gender.NON_BINARY,
}

# ClubHub xlsx header -> row field. Headers are unique in that layout, so a
# plain name lookup works (unlike the Sportadmin layout above).
_CLUBHUB_COLUMNS = {
    "MedlemsNr": None,
    "Förnamn": "first_name",
    "Efternamn": "last_name",
    "Personnummer": "personnummer",
    "Kön": "gender",
    "Adress": "street_address",
    "Postnummer": "postal_code",
    "Stad": "city",
    "E-post": "email",
    "Mobiltelefon": "phone_mobile",
    "Allergi": "allergy",
    "Övrigt": "notes",
    "Roll": "roles",
    "Betalningsstatus": "payment_status",
    "Målsman": "guardians",
    "Vårdnadshavare till": "children",
}

# ClubHub xml tag -> xlsx header.
_CLUBHUB_XML_TAGS = {
    "medlemsnr": "MedlemsNr",
    "fornamn": "Förnamn",
    "efternamn": "Efternamn",
    "personnummer": "Personnummer",
    "kon": "Kön",
    "adress": "Adress",
    "postnummer": "Postnummer",
    "stad": "Stad",
    "epost": "E-post",
    "mobiltelefon": "Mobiltelefon",
    "allergi": "Allergi",
    "ovrigt": "Övrigt",
    "roll": "Roll",
    "betalningsstatus": "Betalningsstatus",
    "malsman": "Målsman",
    "vardnadshavare": "Vårdnadshavare till",
}

_PAYMENT_STATUS_MAP = {
    "betald": Membership.PaymentStatus.PAID,
    "delvis betald": Membership.PaymentStatus.PARTLY_PAID,
    "obetald": Membership.PaymentStatus.UNPAID,
}

# "Medlem, Tränare" (xlsx) or "Medlem; Tränare" (xml) -> canonical labels.
_ROLE_PATTERN = re.compile(r"[,;]")

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


def _split_names(text):
    """Split "Anna Andersson (Mamma); Bo Berg" into (name, relation) pairs."""
    entries = []
    for part in re.split(r"[;]", _clean(text)):
        part = part.strip()
        if not part:
            continue
        match = re.match(r"^(.*?)\s*\((.*?)\)\s*$", part)
        if match:
            entries.append((match.group(1).strip(), match.group(2).strip()))
        else:
            entries.append((part, ""))
    return entries


_ROLE_MAP = {
    "medlem": "Medlem",
    "tränare": "Tränare",
    "admin": "Admin",
    "förälder": "Förälder",
}


def _clubhub_row(fields, line_number):
    """Build an import row dict from a {row_field: raw value} mapping.

    Returns ``None`` for rows without any name. Warnings are embedded in
    the row (same schema as the Sportadmin parser).
    """
    first_name = _clean(fields.get("first_name"))
    last_name = _clean(fields.get("last_name"))
    if not first_name and not last_name:
        return None

    row_warnings = []
    raw_pnr = _clean(fields.get("personnummer")).replace(" ", "")
    personnummer = None
    if raw_pnr:
        try:
            personnummer = normalize_personnummer(raw_pnr)
        except ValidationError:
            row_warnings.append(translate("Ogiltigt personnummer hoppas över.", AREA))

    email = _valid_email(fields.get("email"))
    if _clean(fields.get("email")) and not email:
        row_warnings.append(translate("Ogiltig e-postadress hoppas över.", AREA))

    roles = []
    for part in _ROLE_PATTERN.split(_clean(fields.get("roles"))):
        role = _ROLE_MAP.get(part.strip().lower())
        if role:
            roles.append(role)

    return {
        "first_name": first_name,
        "last_name": last_name,
        "personnummer": personnummer,
        "gender": _GENDER_MAP.get(_clean(fields.get("gender")).lower(), ""),
        "street_address": _clean(fields.get("street_address")),
        "postal_code": _clean(fields.get("postal_code")),
        "city": _clean(fields.get("city")),
        "email": email,
        "phone_mobile": _clean(fields.get("phone_mobile")),
        "notes": _clean(fields.get("notes")),
        "allergy": _clean(fields.get("allergy")),
        "start_date": "",
        "payment_status": _clean(fields.get("payment_status")),
        "roles": roles,
        "guardians": [
            {"name": name, "relation": relation, "email": "", "phone": ""}
            for name, relation in _split_names(fields.get("guardians"))
        ],
        "children": [name for name, _ in _split_names(fields.get("children"))],
        "warnings": row_warnings,
    }


def parse_sportadmin_personregister(data):
    """Parse an xlsx byte stream into ``(rows, warnings)``.

    Accepts both the Sportadmin export and the ClubHub export (detected by
    the "Roll"/"Betalningsstatus" headers). Each row is a JSON-serializable
    dict with the Person fields plus ``guardians``/``children`` lists and,
    for the ClubHub layout, ``roles`` and ``payment_status``. Rows that
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

    header_names = [_clean(cell) for cell in header]

    if "Roll" in header_names or "Betalningsstatus" in header_names:
        # ClubHub layout: unique headers, resolved by name.
        column_fields = [_CLUBHUB_COLUMNS.get(name) for name in header_names]
        rows, warnings = [], []
        for line_number, row in enumerate(excel_rows, start=2):
            if row is None or not any(_clean(cell) for cell in row):
                continue
            fields = {}
            for index, field in enumerate(column_fields):
                if field:
                    fields[field] = row[index] if index < len(row) else None
            parsed = _clubhub_row(fields, line_number)
            if parsed is None:
                continue
            rows.append(parsed)
            for warning in parsed["warnings"]:
                warnings.append(
                    f"{parsed['first_name']} {parsed['last_name']} (rad {line_number}): {warning}"
                )
        return rows, warnings

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
                "payment_status": "",
                "roles": [],
                "guardians": guardians,
                "children": [],
                "warnings": row_warnings,
            }
        )
        for warning in row_warnings:
            warnings.append(f"{first_name} {last_name} (rad {line_number}): {warning}")

    return rows, warnings


def parse_personregister_xml(data):
    """Parse a ClubHub xml export into ``(rows, warnings)``.

    Accepts a byte stream or string; raises ``ET.ParseError`` on malformed
    xml (the caller reports a friendly error).
    """
    if isinstance(data, bytes):
        text = data.decode("utf-8", errors="replace")
    else:
        text = data
    root = ET.fromstring(text)
    rows, warnings = [], []
    for line_number, node in enumerate(root.iter("person"), start=2):
        fields = {}
        for child in node:
            header = _CLUBHUB_XML_TAGS.get(child.tag)
            if header is not None:
                field = _CLUBHUB_COLUMNS[header]
                if field:
                    fields[field] = child.text
        parsed = _clubhub_row(fields, line_number)
        if parsed is None:
            continue
        rows.append(parsed)
        for warning in parsed["warnings"]:
            warnings.append(
                f"{parsed['first_name']} {parsed['last_name']} (rad {line_number}): {warning}"
            )
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
        match = name_match.filter(email=data["email"]).first()
        if match is not None:
            return match
        # Guardians created from denormalized text have no email; a later
        # full row for the same person should still match them.
        return name_match.filter(email="").first()
    return name_match.filter(email="").first()


def _find_or_create_named_person(club, name, email="", phone=""):
    """Match a denormalized name ("Förnamn Efternamn") to a Person, or create one."""
    name_parts = name.split(" ", 1)
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) > 1 else ""
    email = _valid_email(email)
    if email:
        person = Person.objects.filter(club=club, email=email).first()
        if person is not None:
            return person
    query = Person.objects.filter(club=club, first_name=first_name, last_name=last_name)
    if email:
        person = query.filter(email="").first()
    else:
        person = query.filter(personnummer__isnull=True).first() or query.first()
    if person is None:
        person = Person.objects.create(
            club=club,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone_mobile=_clean(phone),
        )
    elif email and not person.email:
        person.email = email
        person.save()
    return person


def import_person_rows(club, rows):
    """Create Person/GuardianRelation/Membership/StaffProfile records from parsed rows.

    Returns ``(created, skipped)`` counts. Rows matching an existing person
    (full/masked personnummer, or name+email for pnr-less rows) are skipped,
    making re-imports safe. ClubHub-export rows additionally restore roles
    (membership, trainer/admin staff profile), payment status and the
    guardian-of relation ("Vårdnadshavare till").
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
            # A guardian created from denormalized text may be matched by a
            # full row carrying the missing email — backfill it.
            if data.get("email") and not existing.email:
                existing.email = data["email"]
                existing.save()
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
            guardian = _find_or_create_named_person(
                club,
                guardian_data["name"],
                email=guardian_data.get("email", ""),
                phone=guardian_data.get("phone", ""),
            )
            GuardianRelation.objects.get_or_create(
                guardian=guardian,
                child=person,
                defaults={"relation": _clean(guardian_data.get("relation", ""))},
            )

        # "Vårdnadshavare till" from a ClubHub export: this person is the
        # guardian of the named children.
        for child_name in data.get("children", []):
            child = _find_or_create_named_person(club, child_name)
            GuardianRelation.objects.get_or_create(
                guardian=person, child=child, defaults={"relation": ""}
            )

        roles = data.get("roles") or []
        start_date = data.get("start_date")
        if "Medlem" in roles or start_date:
            payment = _PAYMENT_STATUS_MAP.get(
                _clean(data.get("payment_status")).lower(), ""
            )
            Membership.objects.get_or_create(
                person=person,
                defaults={
                    "status": Membership.Status.ACTIVE,
                    "start_date": start_date or date.today(),
                    "payment_status": payment or Membership.PaymentStatus.UNPAID,
                },
            )

        if "Tränare" in roles or "Admin" in roles:
            profile, _ = StaffProfile.objects.get_or_create(person=person)
            if "Admin" in roles and not profile.is_admin:
                profile.is_admin = True
                profile.save()

        created += 1
    return created, skipped
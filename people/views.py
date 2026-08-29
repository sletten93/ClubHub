import io
import json
import xml.etree.ElementTree as ET
from datetime import date, timedelta

import openpyxl
from django.contrib import messages
from django.db.models import (
    CharField,
    Exists,
    F,
    OuterRef,
    Prefetch,
    Q,
    Value,
)
from django.db.models.functions import Concat, Substr
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.views.generic import (
    CreateView,
    DeleteView,
    ListView,
    UpdateView,
    View,
)

from clubs.mixins import TablePaginationMixin
from clubs.translations import translate
from groups.models import GroupMembership
from people.mixins import AdminRequiredMixin

from . import services
from .forms import PersonForm
from .sportadmin import (
    import_person_rows,
    parse_personregister_xml,
    parse_sportadmin_personregister,
)
from .models import GuardianRelation, Membership, Person


ROLE_FILTERS = ("member", "trainer", "guardian", "other")
PAYMENT_FILTERS = ("paid", "partly", "unpaid")
GENDER_FILTERS = tuple(Person.Gender.values)
AGE_FILTERS = ("over15", "under15")


class PersonRegisterQuerysetMixin:
    """Search/filter/sort logic shared by the register table and exports.

    Every filter is off unless the query string explicitly asks for it —
    an absent or empty checkbox group means "no filtering", never
    "match nothing". Persons with no gender set match no gender filter.
    """

    # Whitelisted sort keys -> model fields. Names are the stable tiebreaker
    # for all other columns so equal values keep a predictable order.
    SORT_FIELDS = {
        "nr": ["member_number"],
        "name": ["last_name", "first_name"],
        "pnr": ["personnummer"],
        "email": ["email"],
        "phone": ["phone_mobile"],
    }

    def _parse_params(self):
        params = self.request.GET
        self._search = params.get("q", "").strip()
        self._roles = [f for f in params.getlist("role") if f in ROLE_FILTERS]
        self._payments = [f for f in params.getlist("payment") if f in PAYMENT_FILTERS]
        self._ages = [f for f in params.getlist("age") if f in AGE_FILTERS]
        self._genders = [f for f in params.getlist("gender") if f in GENDER_FILTERS]
        sort = params.get("sort", "nr")
        self._sort = sort if sort in self.SORT_FIELDS else "nr"
        direction = params.get("dir", "asc")
        self._direction = direction if direction in ("asc", "desc") else "asc"

    def build_queryset(self):
        queryset = (
            Person.objects.filter(club=services.get_person(self.request.user).club)
            .select_related("user")
            .annotate(
                # Combined first + last name so "Anna Andersson" matches as-is.
                search_name=Concat(
                    "first_name", Value(" "), "last_name", output_field=CharField()
                )
            )
        )

        if self._search:
            query = (
                Q(member_number__icontains=self._search)
                | Q(first_name__icontains=self._search)
                | Q(last_name__icontains=self._search)
                | Q(personnummer__icontains=self._search)
                | Q(email__icontains=self._search)
                | Q(phone_mobile__icontains=self._search)
                | Q(search_name__icontains=self._search)
            )
            queryset = queryset.filter(query)

        membership_of = Membership.objects.filter(person=OuterRef("pk"))

        if self._roles:
            # All three markers are annotated whenever roles are filtered so
            # "other" (no marker at all) can negate them.
            queryset = queryset.annotate(
                has_membership=Exists(membership_of),
                has_trainer_role=Exists(
                    GroupMembership.objects.filter(
                        person=OuterRef("pk"), role=GroupMembership.Role.TRAINER
                    )
                ),
                has_guarded_children=Exists(
                    GuardianRelation.objects.filter(guardian=OuterRef("pk"))
                ),
            )
            role_query = Q()
            if "member" in self._roles:
                role_query |= Q(has_membership=True)
            if "trainer" in self._roles:
                role_query |= Q(has_trainer_role=True)
            if "guardian" in self._roles:
                role_query |= Q(has_guarded_children=True)
            if "other" in self._roles:
                role_query |= (
                    Q(has_membership=False)
                    & Q(has_trainer_role=False)
                    & Q(has_guarded_children=False)
                )
            queryset = queryset.filter(role_query)


        if self._payments:
            annotations = {}
            if "paid" in self._payments:
                annotations["has_paid_membership"] = Exists(
                    membership_of.filter(payment_status=Membership.PaymentStatus.PAID)
                )
            if "partly" in self._payments:
                annotations["has_partly_paid_membership"] = Exists(
                    membership_of.filter(
                        payment_status=Membership.PaymentStatus.PARTLY_PAID
                    )
                )
            if "unpaid" in self._payments:
                annotations["has_unpaid_membership"] = Exists(
                    membership_of.filter(payment_status=Membership.PaymentStatus.UNPAID)
                )
            queryset = queryset.annotate(**annotations)
            payment_query = Q()
            if "paid" in self._payments:
                payment_query |= Q(has_paid_membership=True)
            if "partly" in self._payments:
                payment_query |= Q(has_partly_paid_membership=True)
            if "unpaid" in self._payments:
                payment_query |= Q(has_unpaid_membership=True)
            queryset = queryset.filter(payment_query)

        if self._genders:
            queryset = queryset.filter(gender__in=self._genders)

        if self._ages:
            # Age is derived from the personnummer date part (first 8 chars).
            # Persons without a personnummer match neither filter.
            today = date.today()
            try:
                cutoff = today.replace(year=today.year - 15)
            except ValueError:  # born on 29 February
                cutoff = today.replace(year=today.year - 15, day=28)
            next_day = cutoff + timedelta(days=1)
            queryset = queryset.annotate(
                birth_date_part=Substr("personnummer", 1, 8, output_field=CharField())
            )
            age_query = Q()
            if "over15" in self._ages:
                age_query |= Q(birth_date_part__lte=cutoff.strftime("%Y%m%d"))
            if "under15" in self._ages:
                age_query |= Q(birth_date_part__gte=next_day.strftime("%Y%m%d"))
            queryset = queryset.filter(age_query)

        ordering = []
        for name in self.SORT_FIELDS[self._sort]:
            field = F(name)
            ordering.append(
                field.desc(nulls_last=True)
                if self._direction == "desc"
                else field.asc(nulls_last=True)
            )
        if self._sort != "name":
            ordering.extend([F("last_name").asc(), F("first_name").asc()])
        return queryset.order_by(*ordering)


class PersonRegisterView(
    TablePaginationMixin, PersonRegisterQuerysetMixin, AdminRequiredMixin, ListView
):
    """Person register with search, filters and sortable columns."""

    template_name = "people/person_register.html"
    context_object_name = "people"

    def get_queryset(self):
        self._parse_params()
        return self.build_queryset()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        base_params = self.request.GET.copy()
        for key in ("sort", "dir", "page"):
            base_params.pop(key, None)

        def sort_url(key, direction):
            params = base_params.copy()
            params["sort"] = key
            params["dir"] = direction
            return f"?{params.urlencode()}"

        columns = []
        for key, label, width in (
            ("nr", translate("Nr", "Personregister"), "70px"),
            ("name", translate("Namn"), None),
            ("pnr", translate("Personnummer", "Personregister"), None),
            ("email", translate("E-post", "Personregister"), None),
            ("phone", translate("Mobiltelefon", "Personregister"), None),
        ):
            # Inactive columns advertise ascending sort on hover; the active
            # column shows its current direction and toggles when clicked.
            # Ascending shows a down arrow, descending an up arrow.
            if key == self._sort and self._direction == "desc":
                url, icon = sort_url(key, "asc"), "fa-arrow-up"
            else:
                url, icon = sort_url(key, "desc"), "fa-arrow-down"
            columns.append(
                {"key": key, "label": label, "width": width, "url": url, "icon": icon}
            )

        context.update(
            {
                "search": self._search,
                "active_filters": {
                    "role": self._roles,
                    "payment": self._payments,
                    "age": self._ages,
                    "gender": self._genders,
                },
                "is_filtered": bool(
                    self._search
                    or self._roles
                    or self._payments
                    or self._ages
                    or self._genders
                ),
                "sort": self._sort,
                "dir": self._direction,
                "columns": columns,
            }
        )
        return context


def _gender_text(person):
    return person.get_gender_display() or ""


def _roles_text(person):
    """Comma-separated role labels matching the register table's role filter."""
    roles = []
    if hasattr(person, "membership"):
        roles.append("Medlem")
    if any(
        gm.role == GroupMembership.Role.TRAINER
        for gm in person.group_memberships.all()
    ):
        roles.append("Tränare")
    staff = getattr(person, "staff_profile", None)
    if staff is not None and staff.is_admin:
        roles.append("Admin")
    if person.guardian_of.exists():
        roles.append("Förälder")
    return ", ".join(roles)


def _payment_text(person):
    membership = getattr(person, "membership", None)
    if membership is None:
        return ""
    return membership.get_payment_status_display()


def _guardians_text(person):
    return "; ".join(
        f"{rel.guardian.full_name} ({rel.relation})".strip()
        if rel.relation
        else rel.guardian.full_name
        for rel in person.guarded_by.all()
    )


def _children_text(person):
    return "; ".join(rel.child.full_name for rel in person.guardian_of.all())


class PersonExportView(PersonRegisterQuerysetMixin, AdminRequiredMixin, View):
    """Download the register as xlsx or xml, honouring search/filters/sort.

    Headers use Swedish names shared with the Sportadmin columns so an
    export can be re-imported (both formats are accepted by the import).
    Pagination never applies: every matching row is included regardless of
    the current page size.
    """

    # xlsx header, xml tag, model attribute or value callable
    EXPORT_COLUMNS = [
        ("MedlemsNr", "medlemsnr", "member_number"),
        ("Förnamn", "fornamn", "first_name"),
        ("Efternamn", "efternamn", "last_name"),
        ("Personnummer", "personnummer", "personnummer"),
        ("Kön", "kon", _gender_text),
        ("Adress", "adress", "street_address"),
        ("Postnummer", "postnummer", "postal_code"),
        ("Stad", "stad", "city"),
        ("E-post", "epost", "email"),
        ("Mobiltelefon", "mobiltelefon", "phone_mobile"),
        ("Allergi", "allergi", "allergy"),
        ("Övrigt", "ovrigt", "notes"),
        ("Roll", "roll", _roles_text),
        ("Betalningsstatus", "betalningsstatus", _payment_text),
        ("Målsman", "malsman", _guardians_text),
        ("Vårdnadshavare till", "vardnadshavare", _children_text),
    ]

    def get(self, request, *args, **kwargs):
        export_format = request.GET.get("format", "xlsx")
        if export_format not in ("xlsx", "xml"):
            export_format = "xlsx"
        self._parse_params()
        persons = self.build_queryset().prefetch_related(
            "membership",
            "staff_profile",
            "group_memberships",
            Prefetch(
                "guardian_of", queryset=GuardianRelation.objects.select_related("child")
            ),
            Prefetch(
                "guarded_by",
                queryset=GuardianRelation.objects.select_related("guardian"),
            ),
        )
        if export_format == "xml":
            payload = self._render_xml(persons)
            content_type = "text/xml; charset=utf-8"
        else:
            payload = self._render_xlsx(persons)
            content_type = (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        filename = f"personregister-{date.today().isoformat()}.{export_format}"
        response = HttpResponse(payload, content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    @classmethod
    def _cell(cls, person, getter):
        value = getter(person) if callable(getter) else getattr(person, getter)
        return "" if value is None else value

    @classmethod
    def _render_xlsx(cls, persons):
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.title = "Personregister"
        sheet.append([header for header, _, _ in cls.EXPORT_COLUMNS])
        for person in persons:
            sheet.append(
                [cls._cell(person, attr) for _, _, attr in cls.EXPORT_COLUMNS]
            )
        buffer = io.BytesIO()
        workbook.save(buffer)
        return buffer.getvalue()

    @classmethod
    def _render_xml(cls, persons):
        root = ET.Element("personregister")
        for person in persons:
            node = ET.SubElement(root, "person")
            for _, tag, attr in cls.EXPORT_COLUMNS:
                ET.SubElement(node, tag).text = str(cls._cell(person, attr))
        ET.indent(root)
        return ET.tostring(root, encoding="UTF-8", xml_declaration=True)


class PersonCreateView(AdminRequiredMixin, CreateView):
    model = Person
    form_class = PersonForm
    template_name = "shared/object_form.html"
    success_url = reverse_lazy("people:register")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = translate("Ny person", "Personregister")
        context["cancel_url"] = reverse_lazy("people:register")
        return context

    def form_valid(self, form):
        form.instance.club = services.get_person(self.request.user).club
        response = super().form_valid(form)
        messages.success(
            self.request, translate("Personen har skapats.", "Personregister")
        )
        return response


class PersonUpdateView(AdminRequiredMixin, UpdateView):
    model = Person
    form_class = PersonForm
    template_name = "shared/object_form.html"
    context_object_name = "object"

    def get_queryset(self):
        return Person.objects.filter(club=services.get_person(self.request.user).club)

    def get_success_url(self):
        return reverse_lazy("people:register")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = translate("Ändra person", "Personregister")
        context["cancel_url"] = reverse_lazy("people:register")
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request, translate("Personen har uppdaterats.", "Personregister")
        )
        return response


class PersonDeleteView(AdminRequiredMixin, DeleteView):
    template_name = "shared/confirm_delete.html"
    success_url = reverse_lazy("people:register")

    def get_queryset(self):
        return Person.objects.filter(club=services.get_person(self.request.user).club)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["cancel_url"] = reverse_lazy("people:register")
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request, translate("Personen har tagits bort.", "Personregister")
        )
        return response


SESSION_KEY = "sportadmin_import_rows"


def _preview_row_meta(row):
    """Filter metadata for one preview row's select checkbox.

    Uses the register filter vocabulary (gender values, under15/over15,
    member/trainer/admin/parent) as space-separated data attributes so the
    preview's filter button can check/uncheck rows client-side. A row is a
    "member" exactly when the import would create a Membership (explicit
    role or a start date); "parent" comes from the ClubHub export's
    "Vårdnadshavare till" column. Age uses the same under-15 cutoff as the
    register; rows without personnummer match neither age.
    """
    roles = row.get("roles") or []
    types = []
    if "Medlem" in roles or row.get("start_date"):
        types.append("member")
    if "Tränare" in roles:
        types.append("trainer")
    if "Admin" in roles:
        types.append("admin")
    if "Förälder" in roles or row.get("children"):
        types.append("parent")

    age = ""
    personnummer = row.get("personnummer") or ""
    if len(personnummer) >= 8:
        today = date.today()
        try:
            cutoff = today.replace(year=today.year - 15)
        except ValueError:  # born on 29 February
            cutoff = today.replace(year=today.year - 15, day=28)
        if personnummer[:8] <= cutoff.strftime("%Y%m%d"):
            age = "over15"
        else:
            age = "under15"
    return {"age": age, "types": " ".join(types)}


class PersonImportPreviewView(AdminRequiredMixin, View):
    """Analyze an uploaded Sportadmin xlsx and show a confirmation table."""

    http_method_names = ["post"]

    def post(self, request):
        upload = request.FILES.get("file")
        if upload is None:
            messages.error(request, translate("Ingen fil valdes.", "Personregister"))
            return redirect("people:register")
        name = upload.name.lower()
        if name.endswith(".xml"):
            try:
                rows, warnings = parse_personregister_xml(upload.read())
            except Exception:
                messages.error(
                    request,
                    translate("Filen kunde inte läsas.", "Personregister"),
                )
                return redirect("people:register")
        elif name.endswith(".xlsx"):
            try:
                rows, warnings = parse_sportadmin_personregister(upload.read())
            except Exception:
                messages.error(
                    request,
                    translate(
                        "Filen kunde inte läsas som ett Excel-register.", "Personregister"
                    ),
                )
                return redirect("people:register")
        else:
            messages.error(
                request,
                translate(
                    "Filen måste vara i xlsx- eller xml-format.", "Personregister"
                ),
            )
            return redirect("people:register")
        if not rows:
            messages.error(
                request, translate("Inga personer hittades i filen.", "Personregister")
            )
            return redirect("people:register")

        request.session[SESSION_KEY] = json.dumps(rows)
        request.session.modified = True
        # Annotate copies for rendering (the stored rows stay canonical);
        # row order is preserved so checkbox values are session indices.
        return render(
            request,
            "people/person_import_preview.html",
            {
                "rows": [dict(row, **_preview_row_meta(row)) for row in rows],
                "warnings": warnings,
            },
        )


@method_decorator(require_POST, name="dispatch")
class PersonImportConfirmView(AdminRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request):
        raw = request.session.pop(SESSION_KEY, None)
        if not raw:
            messages.error(
                request,
                translate(
                    "Importen har upphört att gälla. Ladda upp filen igen.",
                    "Personregister",
                ),
            )
            return redirect("people:register")
        rows = json.loads(raw)
        # Checkbox values are indices into the stored row list; an absent or
        # empty selection imports nothing.
        selected = set(request.POST.getlist("selected"))
        rows = [row for index, row in enumerate(rows) if str(index) in selected]
        if not rows:
            messages.error(
                request,
                translate("Inga personer valdes för import.", "Personregister"),
            )
            return redirect("people:register")
        club = services.get_person(request.user).club
        created, skipped = import_person_rows(club, rows)
        message = translate(
            "%(created)d personer importerades, %(skipped)d fanns redan.",
            "Personregister",
        ) % {"created": created, "skipped": skipped}
        messages.success(request, message)
        return redirect("people:register")
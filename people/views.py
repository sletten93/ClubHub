import json

from django.contrib import messages
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

from clubs.translations import translate
from people.mixins import AdminRequiredMixin

from . import services
from .forms import PersonForm
from .sportadmin import import_person_rows, parse_sportadmin_personregister
from .models import Person


class PersonRegisterView(AdminRequiredMixin, ListView):
    template_name = "people/person_register.html"
    context_object_name = "people"

    def get_queryset(self):
        return (
            Person.objects.filter(club=services.get_person(self.request.user).club)
            .select_related("user")
            .order_by("last_name", "first_name")
        )


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


class PersonImportPreviewView(AdminRequiredMixin, View):
    """Analyze an uploaded Sportadmin xlsx and show a confirmation table."""

    http_method_names = ["post"]

    def post(self, request):
        upload = request.FILES.get("file")
        if upload is None:
            messages.error(request, translate("Ingen fil valdes.", "Personregister"))
            return redirect("people:register")
        if not upload.name.lower().endswith(".xlsx"):
            messages.error(
                request, translate("Filen måste vara i xlsx-format.", "Personregister")
            )
            return redirect("people:register")
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
        if not rows:
            messages.error(
                request, translate("Inga personer hittades i filen.", "Personregister")
            )
            return redirect("people:register")

        request.session[SESSION_KEY] = json.dumps(rows)
        request.session.modified = True
        return render(
            request,
            "people/person_import_preview.html",
            {"rows": rows, "warnings": warnings},
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
        club = services.get_person(request.user).club
        created, skipped = import_person_rows(club, rows)
        message = translate(
            "%(created)d personer importerades, %(skipped)d fanns redan.",
            "Personregister",
        ) % {"created": created, "skipped": skipped}
        messages.success(request, message)
        return redirect("people:register")
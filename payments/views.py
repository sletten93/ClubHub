from decimal import Decimal

from django.contrib import messages
from django.db.models import Count, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView

from clubs.translations import translate
from people import services
from people.mixins import AdminRequiredMixin

from .forms import PaymentForm
from .models import Fee, Invoice, Payment


class InvoiceListView(AdminRequiredMixin, ListView):
    template_name = "payments/invoice_list.html"
    context_object_name = "invoices"
    paginate_by = 50

    def get_queryset(self):
        person = services.get_person(self.request.user)
        queryset = (
            Invoice.objects.filter(club=person.club)
            .select_related("person", "season")
            # paid_total preloads the row-level sum so the template doesn't
            # trigger one aggregate query per invoice (Invoice.paid_amount).
            .annotate(paid_total=Coalesce(Sum("payments__amount"), Value(Decimal("0.00"))))
            .order_by("-created_at")
        )
        status = self.request.GET.get("status")
        if status and status in Invoice.Status.values:
            queryset = queryset.filter(status=status)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        person = services.get_person(self.request.user)
        status_counts = dict(
            Invoice.objects.filter(club=person.club)
            .values("status")
            .annotate(n=Count("id"))
            .values_list("status", "n")
        )
        context["statuses"] = Invoice.Status.choices
        context["current_status"] = self.request.GET.get("status", "")
        context["fees"] = Fee.objects.filter(club=person.club).select_related("season")
        context["status_tabs"] = [
            {
                "value": status,
                "label": label,
                "count": status_counts.get(status, 0),
            }
            for status, label in Invoice.Status.choices
        ]
        return context


class InvoiceDetailView(AdminRequiredMixin, DetailView):
    template_name = "payments/invoice_detail.html"
    context_object_name = "invoice"

    def get_queryset(self):
        person = services.get_person(self.request.user)
        return Invoice.objects.filter(club=person.club).select_related("person", "season")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = PaymentForm(
            initial={
                "amount": self.object.remaining_amount,
                "paid_on": timezone.localdate(),
                "method": Payment.Method.SWISH,
            }
        )
        return context


@require_POST
def register_payment(request, pk):
    person = services.get_person(request.user)
    invoice = get_object_or_404(Invoice, pk=pk, club=person.club)
    form = PaymentForm(request.POST)
    if form.is_valid():
        payment = form.save(commit=False)
        payment.invoice = invoice
        payment.registered_by = person
        payment.save()
        messages.success(
            request, translate("Betalningen har registrerats.", "Fakturor")
        )
    else:
        messages.error(
            request,
            translate(
                "Kunde inte registrera betalningen. Kontrollera belopp och datum.",
                "Fakturor",
            ),
        )
    return redirect("payments:detail", pk=invoice.pk)

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from clubs.models import Club
from people.models import Person
from scheduling.models import Season


class Fee(models.Model):
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name="fees")
    name = models.CharField(max_length=200)
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    season = models.ForeignKey(
        Season, on_delete=models.PROTECT, null=True, blank=True, related_name="fees"
    )
    description = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["club", "name"], name="uniq_fee_per_club")
        ]

    def __str__(self):
        return f"{self.name} ({self.amount} kr)"


class Invoice(models.Model):
    class Status(models.TextChoices):
        UNPAID = "unpaid", "Obetald"
        PARTLY_PAID = "partly_paid", "Delvis betald"
        PAID = "paid", "Betald"
        CANCELLED = "cancelled", "Makulerad"

    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name="invoices")
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="invoices")
    fee = models.ForeignKey(
        Fee, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices"
    )
    season = models.ForeignKey(
        Season, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices"
    )
    title = models.CharField(max_length=200)
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UNPAID)
    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["club", "status"])]

    @property
    def paid_amount(self):
        total = self.payments.aggregate(total=models.Sum("amount"))["total"]
        return total or Decimal("0")

    @property
    def remaining_amount(self):
        return max(self.amount - self.paid_amount, Decimal("0"))

    def recalc_status(self):
        if self.status == self.Status.CANCELLED:
            return
        paid = self.paid_amount
        if paid >= self.amount:
            new_status = self.Status.PAID
        elif paid > 0:
            new_status = self.Status.PARTLY_PAID
        else:
            new_status = self.Status.UNPAID
        if new_status != self.status:
            self.status = new_status
            self.save(update_fields=["status", "updated_at"])

    def __str__(self):
        return f"{self.title} - {self.person.full_name} ({self.get_status_display()})"


class Payment(models.Model):
    class Method(models.TextChoices):
        SWISH = "swish", "Swish"
        CASH = "cash", "Kontant"
        BANK_TRANSFER = "bank_transfer", "Banköverföring"
        OTHER = "other", "Övrigt"

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    paid_on = models.DateField(default=timezone.localdate)
    method = models.CharField(max_length=20, choices=Method.choices, default=Method.SWISH)
    registered_by = models.ForeignKey(
        Person,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments_registered",
    )
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-paid_on"]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.invoice.recalc_status()

    def delete(self, *args, **kwargs):
        invoice = self.invoice
        super().delete(*args, **kwargs)
        invoice.recalc_status()

    def __str__(self):
        return f"{self.amount} kr mot {self.invoice}"

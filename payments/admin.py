from django.contrib import admin

from .models import Fee, Invoice, Payment


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0


@admin.register(Fee)
class FeeAdmin(admin.ModelAdmin):
    list_display = ("name", "club", "amount", "season")
    list_filter = ("club", "season")
    search_fields = ("name",)


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("person", "title", "amount", "status", "due_date", "created_at")
    list_filter = ("status", "club")
    search_fields = ("person__first_name", "person__last_name", "title")
    inlines = [PaymentInline]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("invoice", "amount", "paid_on", "method", "registered_by")
    list_filter = ("method",)

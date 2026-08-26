from django import forms
from django.utils import timezone

from clubs.form_base import TrModelForm

from .models import Payment


class PaymentForm(TrModelForm):
    label_area = "Fakturor"
    labels = {"amount": "Belopp", "paid_on": "Datum", "method": "Metod", "note": "Notering"}

    class Meta:
        model = Payment
        fields = ["amount", "paid_on", "method", "note"]
        widgets = {
            "paid_on": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, initial=None, **kwargs):
        super().__init__(*args, initial=initial, **kwargs)
        for field in self.fields.values():
            css_class = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{css_class} form-control".strip()

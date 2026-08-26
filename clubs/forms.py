from django import forms

from .form_base import TrModelForm
from .models import Club


class PrettyClearableFileInput(forms.ClearableFileInput):
    template_name = "clubs/widgets/pretty_file_input.html"

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        widget = context["widget"]
        filename = ""
        file_url = ""
        file_value = widget.get("value")
        if file_value and hasattr(file_value, "url"):
            file_url = file_value.url
            filename = str(file_value).replace("\\", "/").rsplit("/", 1)[-1]
            if len(filename) > 25:
                filename = filename[:24] + "…"
        widget["display_filename"] = filename
        widget["file_url"] = file_url
        return context


class ClubSettingsForm(TrModelForm):
    label_area = "Klubbinställningar"
    labels = {
        "name": "Namn",
        "organisation_number": "Organisationsnummer",
        "email": "E-post",
        "phone": "Telefon",
        "street_address": "Gatuadress",
        "postal_code": "Postnummer",
        "city": "Ort",
        "primary_color": "Primärfärg",
        "secondary_color": "Sekundärfärg",
        "logo": "Logotyp",
        "background_image": "Bakgrundsbild",
    }

    class Meta:
        model = Club
        fields = [
            "name",
            "organisation_number",
            "email",
            "phone",
            "street_address",
            "postal_code",
            "city",
            "primary_color",
            "secondary_color",
            "logo",
            "background_image",
        ]
        widgets = {
            "primary_color": forms.TextInput(attrs={"type": "color"}),
            "secondary_color": forms.TextInput(attrs={"type": "color"}),
            "logo": PrettyClearableFileInput,
            "background_image": PrettyClearableFileInput,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            widget = field.widget
            if name in ("logo", "background_image"):
                continue
            if getattr(widget, "input_type", "") == "color":
                continue
            css_class = widget.attrs.get("class", "")
            widget.attrs["class"] = f"{css_class} form-control".strip()

    def clean_primary_color(self):
        return self.cleaned_data["primary_color"].lower()

    def clean_secondary_color(self):
        return self.cleaned_data["secondary_color"].lower()

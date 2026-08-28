from django import forms

from .form_base import TrForm, TrModelForm
from .models import Club, UserProfile
from .translations import LANGUAGE_NAMES, available_languages, translate


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


class UserSettingsForm(TrForm):
    """Account-level settings for the signed-in user (page /settings/)."""

    label_area = "Inställningar"
    labels = {
        "first_name": "Förnamn",
        "last_name": "Efternamn",
        "email": "E-post",
        "language": "Språk",
    }

    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(max_length=254)
    language = forms.ChoiceField(required=False, choices=[("", "")])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["language"].choices = [("", translate("Standard", self.label_area))] + [
            (code, LANGUAGE_NAMES.get(code, code)) for code in available_languages()
        ]

    def save(self, user):
        user.email = self.cleaned_data["email"].strip()
        user.first_name = self.cleaned_data["first_name"].strip()
        user.last_name = self.cleaned_data["last_name"].strip()
        user.save(update_fields=["email", "first_name", "last_name"])
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.language = self.cleaned_data["language"]
        profile.save()
        # Keep the club register (and thereby notifications) on the same address.
        person = getattr(user, "person", None)
        if person is not None and person.email != user.email:
            person.email = user.email
            person.save(update_fields=["email", "updated_at"])
        return profile

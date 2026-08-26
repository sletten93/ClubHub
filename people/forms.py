from django import forms

from clubs.translations import translate

from .models import Person


class PersonForm(forms.ModelForm):
    class Meta:
        model = Person
        fields = [
            "first_name",
            "last_name",
            "personnummer",
            "member_number",
            "gender",
            "street_address",
            "postal_code",
            "city",
            "email",
            "phone_mobile",
            "notes",
            "allergy",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 2}),
            "allergy": forms.Textarea(attrs={"rows": 2}),
        }

    LABELS = {
        "first_name": "Förnamn",
        "last_name": "Efternamn",
        "personnummer": "Personnummer",
        "member_number": "Medlemsnummer",
        "gender": "Kön",
        "street_address": "Gatuadress",
        "postal_code": "Postnummer",
        "city": "Postort",
        "email": "E-post",
        "phone_mobile": "Mobiltelefon",
        "notes": "Anteckningar",
        "allergy": "Allergi",
    }
    AREA = "Personregister"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field, key in self.LABELS.items():
            self.fields[field].label = translate(key, self.AREA)
        self.fields["gender"].choices = [
            (value, translate(label, self.AREA))
            for value, label in Person.Gender.choices
        ]

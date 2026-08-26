from django import forms

from clubs.translations import translate
from groups.models import Group

AUDIENCE_CHOICES = [
    ("all", "Alla aktiva medlemmar"),
    ("groups", "Valda grupper"),
]


class NotificationForm(forms.Form):
    subject = forms.CharField(max_length=200)
    body = forms.CharField(widget=forms.Textarea(attrs={"rows": 8}))
    audience = forms.ChoiceField(choices=AUDIENCE_CHOICES, widget=forms.RadioSelect, initial="all")
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={"size": 6}),
    )

    def __init__(self, *args, club=None, **kwargs):
        super().__init__(*args, **kwargs)
        area = "Meddelanden"
        self.fields["subject"].label = translate("Ämne", area)
        self.fields["body"].label = translate("Meddelande", area)
        self.fields["audience"].label = translate("Mottagare", area)
        self.fields["groups"].label = translate("Grupp", "Allmän")
        self.fields["body"].help_text = translate(
            "Platshållare: first_name och last_name inom dubbla måsvingar ersätts per mottagare.",
            area,
        )
        self.fields["audience"].choices = [
            (value, translate(label, area)) for value, label in AUDIENCE_CHOICES
        ]
        if club:
            self.fields["groups"].queryset = Group.objects.filter(club=club)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("audience") == "groups" and not cleaned.get("groups"):
            raise forms.ValidationError(
                translate("Välj minst en grupp.", "Meddelanden")
            )
        return cleaned

from django import forms

from clubs.translations import translate
from people.models import Person

from .models import Group, GroupMembership


class GroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ["name", "description"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].label = translate("Namn")
        self.fields["description"].label = translate("Beskrivning", "Grupper")


class GroupMembershipForm(forms.Form):
    person = forms.ModelChoiceField(queryset=Person.objects.none())
    role = forms.ChoiceField(choices=GroupMembership.Role.choices)

    def __init__(self, *args, club=None, group=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["person"].label = translate("Namn", "Allmän")
        self.fields["role"].label = translate("Roll", "Grupper")
        self.fields["person"].widget.attrs["class"] = "custom-select"
        self.fields["role"].widget.attrs["class"] = "custom-select"
        if club and group:
            active_ids = group.memberships.filter(left_on__isnull=True).values_list(
                "person_id", flat=True
            )
            self.fields["person"].queryset = (
                Person.objects.filter(club=club)
                .exclude(id__in=active_ids)
                .order_by("last_name", "first_name")
            )

from django import forms

from clubs.form_base import TrModelForm

from .models import Activity, ActivityTemplate, Season


class SeasonForm(TrModelForm):
    label_area = "Schema"
    labels = {"name": "Namn"}

    class Meta:
        model = Season
        fields = ["name", "start_date", "end_date"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }


class ActivityTemplateForm(TrModelForm):
    label_area = "Schema"
    labels = {
        "title": "Titel",
        "season": "Säsong",
        "group": "Grupp",
        "recurrence": "Återkomster",
        "weekday": "Veckodag",
        "location": "Plats",
    }

    class Meta:
        model = ActivityTemplate
        fields = [
            "title",
            "activity_type",
            "season",
            "group",
            "recurrence",
            "weekday",
            "start_time",
            "end_time",
            "start_date",
            "end_date",
            "location",
        ]
        widgets = {
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }


class ActivityForm(TrModelForm):
    label_area = "Schema"
    labels = {
        "title": "Titel",
        "season": "Säsong",
        "group": "Grupp",
        "date": "Datum",
        "location": "Plats",
        "notes": "Notering",
    }

    class Meta:
        model = Activity
        fields = [
            "title",
            "activity_type",
            "season",
            "group",
            "date",
            "start_time",
            "end_time",
            "location",
            "is_cancelled",
            "notes",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
        }

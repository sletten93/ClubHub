from django import forms

from .translations import translate


class TranslateLabelsMixin:
    label_area = "Allmän"
    labels = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, key in self.labels.items():
            if name in self.fields:
                self.fields[name].label = translate(key, self.label_area)
        for field in self.fields.values():
            if getattr(field, "choices", None):
                field.choices = [
                    (value, translate(label, self.label_area))
                    for value, label in field.choices
                ]


class TrForm(TranslateLabelsMixin, forms.Form):
    pass


class TrModelForm(TranslateLabelsMixin, forms.ModelForm):
    pass

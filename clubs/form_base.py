from django import forms

from .translations import translate


class TrModelForm(forms.ModelForm):
    label_area = "Allmän"
    labels = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, key in self.labels.items():
            if name in self.fields:
                self.fields[name].label = translate(key, self.label_area)

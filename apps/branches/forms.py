from django import forms

from .models import Branch, UserBranch


class BranchForm(forms.ModelForm):
    class Meta:
        model = Branch
        fields = ["name", "code", "address", "phone", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                continue
            field.widget.attrs["class"] = "form-control"
        # code is immutable after creation
        if self.instance.pk:
            self.fields["code"].disabled = True


class UserBranchForm(forms.ModelForm):
    class Meta:
        model = UserBranch
        fields = ["user", "role", "is_default"]

    def __init__(self, *args, branch=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._branch = branch
        for name, field in self.fields.items():
            if isinstance(field.widget, (forms.CheckboxInput, forms.Select)):
                if isinstance(field.widget, forms.Select):
                    field.widget.attrs["class"] = "form-select"
                continue
            field.widget.attrs["class"] = "form-control"

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self._branch:
            instance.branch = self._branch
        if commit:
            instance.save()
        return instance


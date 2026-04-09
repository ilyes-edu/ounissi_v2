from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import CustomUser, Employee, Team
from ounissi_app.models import SalaryItem, Terminal


class CustomUserCreationForm(UserCreationForm):
    salary_items = forms.ModelMultipleChoiceField(
        queryset=SalaryItem.objects.all(),
        widget=forms.SelectMultiple(attrs={'class': 'multi_select'}),
        required=False
    )

    class Meta:
        model = CustomUser
        fields = ("username", "email")

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            Employee.objects.create(user=user, salary_items=self.cleaned_data['salary_items'])
        return user


class CustomUserChangeForm(UserChangeForm):
    salary_items = forms.ModelMultipleChoiceField(
        queryset=SalaryItem.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    class Meta:
        model = CustomUser
        fields = ("username", "email")



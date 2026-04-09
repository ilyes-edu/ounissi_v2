from django.shortcuts import render
from django.urls import reverse_lazy
from django.contrib.auth.decorators import login_required
from django.views.generic.edit import CreateView
from django.contrib.auth.mixins import UserPassesTestMixin
from .forms import CustomUserCreationForm
from .models import CustomUser, Employee
from ounissi_app.utils import getLoggedData



class SignUpView(UserPassesTestMixin, CreateView):
    form_class = CustomUserCreationForm
    success_url = reverse_lazy("login")
    template_name = "registration/signup.html"

    def test_func(self):
        return self.request.user.is_superuser or self.request.user.has_perm('auth.add_user')

    def form_valid(self, form):
        user = form.save()
        employee = Employee.objects.create(user=user)
        employee.salary_items.set(form.cleaned_data['salary_items'])
        return super().form_valid(form)

@login_required
def employee_list(request):
    employees = Employee.objects.all()
    context = {'employees': employees,
               'logged_data': getLoggedData(request)}
    return render(request, 'employees/employee_list.html', context)

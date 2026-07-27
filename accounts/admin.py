from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.urls import reverse
from django.utils.html import format_html
from .forms import CustomUserCreationForm, CustomUserChangeForm
from .models import CustomUser, Employee, Rank, Team
import ounissi_app.models
import ounissi_app.forms


class EmployeeInline(admin.StackedInline):
    model = Employee
    can_delete = False


class TeamAdmin(admin.ModelAdmin):
    filter_horizontal = ('employees',)
    list_display = ('name', 'leader')


class TimesheetAdmin(admin.ModelAdmin):
    form = ounissi_app.forms.TimesheetForm
    list_display = ('employee', 'date', 'is_confirmed', 'start_time', 'end_time', 'start_time_2', 'end_time_2', 'start_time_3', 'end_time_3')

    list_filter = ('employee', 'date')

class SalaryItemAdmin(admin.ModelAdmin):
    form = ounissi_app.forms.SalaryItemForm
    list_display = ['name', 'calculation_type']


class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = CustomUser
    list_display = ["email", "username", "view_user_details"]

    # Use 'password1' and 'password2' instead of 'password'
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2'),
        }),
    )

    def view_user_details(self, obj):
        url = reverse('admin:accounts_customuser_change', args=[obj.id])
        return format_html('<a href="{}">View Details</a>', url)

    view_user_details.short_description = 'User Details'
    inlines = [EmployeeInline]

class XpertServerAdmin(admin.ModelAdmin):
    list_display = ['name', 'active']

# class ScheduleAdmin(admin.ModelAdmin):
#     list_display = ['name', 'is_template', 'date']

admin.site.register(Rank)
admin.site.register(Team, TeamAdmin)
admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(ounissi_app.models.ScheduleItem)
admin.site.register(ounissi_app.models.Schedule)
admin.site.register(ounissi_app.models.ScheduleEmployee)
admin.site.register(ounissi_app.models.ScheduleTask)
admin.site.register(ounissi_app.models.Task)
admin.site.register(ounissi_app.models.Terminal)
admin.site.register(ounissi_app.models.SalaryItem, SalaryItemAdmin)
admin.site.register(ounissi_app.models.Employee)
admin.site.register(ounissi_app.models.XpertServer, XpertServerAdmin)
admin.site.register(ounissi_app.models.Timesheet, TimesheetAdmin)
admin.site.register(ounissi_app.models.Salary)
admin.site.register(ounissi_app.models.SalaryDetail)
admin.site.register(ounissi_app.models.Shift)
admin.site.register(ounissi_app.models.TaskType)
admin.site.register(ounissi_app.models.Query)
admin.site.register(ounissi_app.models.Reception)
admin.site.register(ounissi_app.models.TaskGeneration)
admin.site.register(ounissi_app.models.Saisie)
admin.site.register(ounissi_app.models.ReceptionProduit)
admin.site.register(ounissi_app.models.ReceptionVignette)
admin.site.register(ounissi_app.models.ReceptionPlacement)
admin.site.register(ounissi_app.models.StockOperation)
admin.site.register(ounissi_app.models.AssignationEmplacement)





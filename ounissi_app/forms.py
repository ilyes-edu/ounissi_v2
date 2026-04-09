from datetime import date
from django import forms
from django.contrib import admin
from .models import *
from accounts.models import Employee
from .salary_calculator import SalaryCalculator
from .xpertcon import XpertConnect


class TimesheetForm(forms.ModelForm):
    employee = forms.ModelChoiceField(queryset=Employee.objects.all())

    class Meta:
        model = Timesheet
        fields = ['employee', 'date', 'start_time', 'end_time', 'start_time_2', 'end_time_2',
                  'start_time_3', 'end_time_3', 'is_confirmed']


class TimesheetFilterForm(forms.Form):
    start_date = forms.DateField(required=False, widget=forms.TextInput(attrs={'type': 'date'}))
    end_date = forms.DateField(required=False, widget=forms.TextInput(attrs={'type': 'date'}))
    employees = forms.ModelChoiceField(
        queryset=Employee.objects.all().order_by('last_name'),
        empty_label="All",
        required=False,
    )


class SalaryItemForm(forms.ModelForm):
    calculation_types = [
        ('fixed', 'Fixe'),
        ('multiply_days', 'Base Jours'),
        ('multiply_hours', 'Base Heurs'),
        ('percentage', 'Percentage'),
        ('addition', 'Addition'),
        ('deduction', 'Deduction'),
        ('product', 'Produit'),
        ('division', 'Division'),
        ('formula', 'Formule'),
    ]
    # dependent_item = forms.ModelChoiceField(queryset=SalaryItem.objects.all())
    calculation_type = forms.ChoiceField(choices=calculation_types)
    default_value = forms.DecimalField()

    def __init__(self, *args, **kwargs):
        super(SalaryItemForm, self).__init__(*args, **kwargs)
        calculation_type = self.instance.calculation_type if self.instance else 'fixed'  # Use 'fixed' as the default
        if calculation_type in ['multiply_days', 'multiply_hours']:
            self.fields['dependent_item'].required = False  # Set dependent_items as not required

    class Meta:
        model = SalaryItem
        fields = ['name', 'item_type', 'calculation_type', 'dependent_item', 'default_value']


class SalaryDetailForm(forms.ModelForm):
    class Meta:
        model = SalaryDetail
        fields = ['salary_item', 'value', 'base', 'amount']
        widgets = {
            'amount': forms.TextInput(attrs={'readonly': 'readonly'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Populate the dropdown for salary items
        self.fields['salary_item'].queryset = SalaryItem.objects.all()

        # Set the initial value for the amount field
        self.fields['amount'].initial = self.calculate_amount()

    def calculate_amount(self):
        if self.instance.salary_item:
            # Create a SalaryCalculator for the employee and month
            employee = self.instance.salary.employee
            month = self.instance.salary.month
            calculator = SalaryCalculator(employee, month)

            # Call the SalaryCalculator's method to calculate the item amount
            item = self.instance.salary_item
            value = self.instance.value
            amount = calculator.calculate_salary_items(item, value).amount

            return amount
        return 0  # Default amount if no salary item is selected


SalaryDetailFormSet = forms.modelformset_factory(SalaryDetail, fields=['salary_item', 'value', 'base', 'amount'],
                                                 extra=0)


class SalaryFilterForm(forms.Form):
    employee = forms.ModelChoiceField(queryset=Employee.objects.all().order_by('last_name'),
                                      empty_label="All Employees", required=False)
    month = forms.DateField(widget=forms.SelectDateWidget(empty_label=("Choose Year",
                                                                       "Choose Month", "")), required=False)


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['priority']

    # assigned_to = forms.ModelMultipleChoiceField(
    #     queryset=Employee.objects.all(),
    #     widget=forms.SelectMultiple(attrs={'class': 'multi_select'}),
    #     required=False  # Set to True if you want to enforce at least one employee
    # )
    # start = forms.DateField(required=False, widget=forms.TextInput(attrs={'type': 'date'}))
    # end = forms.DateField(required=False, widget=forms.TextInput(attrs={'type': 'date'}))

    priority = forms.ChoiceField(choices=[(1, 'Priorite 1'), (2, 'Priorite 2'), (3, 'Priorite 3'),
                                          (4, 'Priorite 4')], initial=4)

    ORDER_CHOICES = [
        ('task_name', 'Task Name'),
        ('priority', 'Priority'),
        # ('start', 'Start Date'),
        # ('end', 'End Date'),
        # ('completion_rate', 'Completion'),
        # Add other fields you want to support for ordering
    ]

    order_by = forms.ChoiceField(choices=ORDER_CHOICES, required=False)


class TaskCreationForm(forms.ModelForm):
    class Meta:
        model = Task
        exclude = ()  # Add fields to exclude, if any

    priority = forms.ChoiceField(choices=[(1, 'Priorite 1'), (2, 'Priorite 2'), (3, 'Priorite 3'),
                                                         (4, 'Priorite 4')], initial=4)

    responsibility_level = forms.ModelChoiceField(
        queryset=Rank.objects.all(),
        initial=4
    )
    task_description = forms.CharField(required=False, widget=forms.Textarea())
    task_type = forms.ModelChoiceField(
        queryset=TaskType.objects.all(),
        initial=0
    )
    average_duration = forms.DurationField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.initial['priority'] = '4'

#used in scheduledetail1
class ScheduleItemForm(forms.ModelForm):
    # schedule_item_id = forms.IntegerField(widget=forms.HiddenInput())
    # progression_rate = forms.ChoiceField(choices=[
    #     (0, '0%'),
    #     (25, '25%'),
    #     (50, '50%'),
    #     (75, '75%'),
    #     (100, '100%'),
    # ], initial=0)

    class Meta:
        model = ScheduleItem
        fields = '__all__'


ScheduleItemFormset = forms.formset_factory(ScheduleItemForm, extra=1)


class ScheduleItemAddEditForm(forms.Form):
    task = forms.ModelChoiceField(queryset=Task.objects.all(), label='Task')
    employee = forms.ModelChoiceField(queryset=Employee.objects.all(), label='Employee')
    assigned_time = forms.DurationField(label='Assigned Time')
    progression_rate = forms.ChoiceField(choices=[
        (0, '0%'),
        (25, '25%'),
        (50, '50%'),
        (75, '75%'),
        (100, '100%'),
    ], initial=0, required=False)
    task_identifier = forms.CharField(required=False)


    def clean(self):
        cleaned_data = super().clean()  # Get validated data from parent class
        employee = cleaned_data.get('employee')
        task = cleaned_data.get('task')
        if employee and task and employee.rank.value > task.responsibility_level.value:
            raise forms.ValidationError('Selected employee does not have the required rank for this task.')
        return cleaned_data


class ScheduleFilterForm(forms.Form):
    # date = forms.DateField(label='Filter by Date', required=False, widget=forms.TextInput(attrs={'type': 'date'}))
    schedule = forms.ModelChoiceField(queryset=Schedule.objects.none(), label='Filter by Schedule', required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['schedule'].queryset = Schedule.objects.filter(
            is_template=False, schedule_status__gt=0).exclude(schedule_name='Transfer_Schedule').order_by('-date',
                                                                                                        '-start_time',
                                                                                                        '-end_time')


#Scpecific for models only
class ScheduleSelectionForm(forms.Form):
    schedule = forms.ChoiceField(choices=())

    def __init__(self, *args, **kwargs):
        super(ScheduleSelectionForm, self).__init__(*args, **kwargs)
        self.fields['schedule'].choices = [(schedule.id, str(schedule)) for schedule in Schedule.objects.filter(is_template=True)]


class TaskPerformanceFilterForm(forms.Form):
    pass
#     start_date = forms.DateField(required=False, widget=forms.TextInput(attrs={'type': 'date'}))
#     end_date = forms.DateField(required=False, widget=forms.TextInput(attrs={'type': 'date'}))
#     # employee = forms.ModelChoiceField(queryset=Employee.objects.all(), required=False, empty_label='All Employees')
#     employee = forms.ModelMultipleChoiceField(
#         queryset=Employee.objects.all(),
#         widget=forms.SelectMultiple(attrs={'class': 'multi_select'}),
#         required=False  # Set to True if you want to enforce at least one employee
#     )


class ReceptionForm(forms.ModelForm):
    YES_NO_CHOICES = ((None, '-'), (True, 'Oui'), (False, 'Non'))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['supplier'] = forms.ChoiceField(choices=[], label='Fournisseur')
        self.fields['supplier'].choices = self.get_supplier_choices()
        self.fields['supplier'].widget.attrs['class'] = 'select'
        self.fields['supplier'].required = True

        for field_name in ['cold_chain', 'psycho', 'correct_destination', 'products_type']:
            self.fields[field_name].widget = forms.Select(choices=self.YES_NO_CHOICES)
            self.fields[field_name].widget.attrs['required'] = 'required'

        self.fields['correct_destination'].widget = forms.Select(choices=((None, 'Non'), (True, 'Oui')))
        self.fields['correct_destination'].widget.attrs['required'] = 'required'

        # Add a hidden field for task_identifier
        self.fields['task_identifier'] = forms.CharField(widget=forms.HiddenInput(), required=False)

    def clean(self):
        cleaned_data = super().clean()
        for field_name in ['cold_chain', 'psycho', 'correct_destination', 'products_type']:
            value = cleaned_data.get(field_name)
            if value is None:
                raise forms.ValidationError(f"Veuillez choisir une valeur pour {field_name}.")

        # Set the task_identifier based on supplier and ref_tiers
        supplier = cleaned_data.get('supplier')
        ref_tiers = cleaned_data.get('ref_tiers')
        cleaned_data['task_identifier'] = f"{supplier}#{ref_tiers}"

        return cleaned_data

    def get_supplier_choices(self):
        # Fetch suppliers from the database using your XpertConnect class
        suppliers = []
        try:
            xpert_connect = XpertConnect()
            xpert_connect.open_session()
            query = Query.objects.get(name='LISTE FOURNISSEURS')
            results = xpert_connect.run_query(query.query, parameters={})
            xpert_connect.close_session()
            suppliers = [(supplier, supplier) for supplier in results['SupplierName']]
            suppliers.insert(0, ('', ''))
            return suppliers
        except Exception as e:
            # Handle exceptions appropriately
            suppliers.append(("Error:", e))
        return suppliers

    class Meta:
        model = Reception
        fields = ['supplier', 'ref_tiers', 'number_of_packs', 'cold_chain', 'psycho', 'correct_destination',
                  'products_type']
        labels = {
            'supplier': 'Fournisseur',
            'ref_tiers': 'No Facture/BL',
            'number_of_packs': 'Nbr de Colis',
            'cold_chain': 'Produits Frigo',
            'psycho': 'Products Psycho',
            'correct_destination': 'Destination Correcte',
            'products_type': 'ParaPharm?'
        }


class SaisieForm(forms.ModelForm):
    class Meta:
        model = Saisie
        fields = '__all__'  # Include all model fields


class ReceptionProduitForm(forms.ModelForm):
    class Meta:
        model = ReceptionProduit
        fields = '__all__'  # Include all model fields


class ReceptionVignetteForm(forms.ModelForm):
    class Meta:
        model = ReceptionVignette
        fields = '__all__'  # Include all model fields


class ReceptionPlacementForm(forms.ModelForm):
    class Meta:
        model = ReceptionPlacement
        fields = '__all__'  # Include all model fields


#
class AssignationEmplacementForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['emplacement'] = forms.ChoiceField(choices=[], label='Emplacement')
        self.fields['emplacement'].choices = self.get_emplacement_choices()
        self.fields['emplacement'].widget.attrs['class'] = 'select'
        self.fields['emplacement'].required = True

        self.fields['operation'] = forms.ModelMultipleChoiceField(
            queryset=StockOperation.objects.all(),
            widget=forms.CheckboxSelectMultiple(),
        )
        self.fields['date_debut'] = forms.DateField(required=False, widget=forms.TextInput(attrs={'type': 'date'}))
        self.fields['date_fin'] = forms.DateField(required=False, widget=forms.TextInput(attrs={'type': 'date'}))

        # widget = forms.TextInput(attrs={'type': 'date'})

    def get_emplacement_choices(self):
        # Fetch emplacement from the database using your XpertConnect class
        emplacements = []
        try:
            xpert_connect = XpertConnect()
            xpert_connect.open_session()
            query = Query.objects.get(name='LISTE EMPLACEMENT')
            results = xpert_connect.run_query(query.query, query.parameters)
            xpert_connect.close_session()
            emplacements = [(emplacement, emplacement) for emplacement in results['DESIGNATION']]
            emplacements.insert(0, ('', ''))
            return emplacements
        except Exception as e:
            # Handle exceptions appropriately
            emplacements.append(("Error:", e))
        return emplacements

    class Meta:
        model = AssignationEmplacement
        fields = ['emplacement', 'employee', 'date_debut', 'date_fin']
        labels = {
            'emplacement': 'Emplacement',
            'employee': 'Employee',
            'date_debut': 'Debut Assignation',
            'date_fin': 'Fin Asignation',
        }

class XpertServerForm(forms.ModelForm):
    pwd = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = XpertServer
        fields = ['servername', 'database', 'user', 'pwd']


class TerminalForm(forms.ModelForm):
    class Meta:
        model = Terminal
        fields = ('terminal_id', 'ip_address')

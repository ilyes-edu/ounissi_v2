from typing import Any
from datetime import datetime, timedelta
from decimal import Decimal
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError
from accounts.models import Employee, Rank
from . import utils
from django.db.models import F, ExpressionWrapper, fields

User = get_user_model()


class Timesheet(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, default=-1)
    date = models.DateField()
    start_time = models.TimeField(default=None, blank=True)
    end_time = models.TimeField(default=None, null=True, blank=True)
    start_time_2 = models.TimeField(default=None, null=True, blank=True)
    end_time_2 = models.TimeField(default=None, null=True, blank=True)
    start_time_3 = models.TimeField(default=None, null=True, blank=True)
    end_time_3 = models.TimeField(default=None, null=True, blank=True)
    is_confirmed = models.BooleanField(default=False)
    # Any additional fields

    def calculate_working_hours(self):
        delta = timedelta()
        if self.start_time and self.end_time:
            # Calculate the time delta between start_time and end_time
            delta = datetime.combine(datetime.min, self.end_time) - datetime.combine(datetime.min, self.start_time)

            if self.start_time_2 and self.end_time_2:
                # Calculate the time delta between start_time and end_time
                delta = delta + (datetime.combine(datetime.min, self.end_time_2)
                                 - datetime.combine(datetime.min, self.start_time_2))
                if self.start_time_3 and self.end_time_3:
                    # Calculate the time delta between start_time and end_time
                    delta = delta + (datetime.combine(datetime.min, self.end_time_3)
                                     - datetime.combine(datetime.min, self.start_time_3))
        hours = delta.total_seconds() / 3600
        return hours

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['employee', 'date'], name='unique_employee_date')
        ]
    def __str__(self):
        return f"Timesheet for {self.employee} on {self.date}"


# Salary part
class CalculationType(models.TextChoices):
    FIXED = 'fixed', 'Fixed Amount'
    PERCENTAGE = 'percentage', 'Percentage of Another Item'
    ADDITION = 'addition', 'Addition of Another Item'
    DEDUCTION = 'deduction', 'Deduction from Another Item'
    PRODUCT = 'product', 'Product with Another Item'
    DIVISION = 'division', 'Division by Another Item'
    FORMULA = 'formula', 'Custom Formula'
    MULTIPLY_DAYS = 'multiply_days', 'Multiply by Number of Days'
    MULTIPLY_HOURS = 'multiply_hours', 'Multiply by Number of Hours'


class SalaryItem(models.Model):
    EARNING = 'G'
    DEDUCTION = 'R'
    ITEM_TYPE_CHOICES = [
        (EARNING, 'Gain'),
        (DEDUCTION, 'Retenue'),
    ]

    name = models.CharField(max_length=100)
    item_type = models.CharField(max_length=1, choices=ITEM_TYPE_CHOICES)
    calculation_type = models.CharField(
        max_length=20,
        choices=CalculationType.choices,
        default=CalculationType.FIXED,  # You can change the default as needed
    )
    dependent_item = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True)
    default_value = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)

    def save(self, *args, **kwargs):
        # Set dependent_items to None if it's not applicable for this item
        if self.calculation_type in ['multiply_days', 'multiply_hours', 'fixed']:
            self.dependent_item = None
        super(SalaryItem, self).save(*args, **kwargs)

    def __str__(self):
        return self.name


class Salary(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    month = models.DateField()  # Date representing the month of the salary
    start_date = models.DateField(blank=True, null=True)  # Starting date for the timesheet range
    end_date = models.DateField(blank=True, null=True)  # Ending date for the timesheet range
    salary_items = models.ManyToManyField(SalaryItem, through='SalaryDetail')
    total_salary = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.0'))

    def __str__(self):
        return f"Salary for {self.employee} - {self.month}"

    def save(self, *args, **kwargs):
        if not self.end_date:
            self.end_date = self.month - timedelta(days=1)
        if not self.start_date:
            self.start_date = utils.calculate_start_date(self.month)
        # Calculate the total salary and save it
        self.total_salary = utils.calculate_total_salary(self, SalaryDetail)

        super(Salary, self).save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['employee', 'month'], name='unique_employee_month')
        ]


class SalaryDetail(models.Model):
    salary = models.ForeignKey(Salary, on_delete=models.CASCADE)
    salary_item = models.ForeignKey(SalaryItem, on_delete=models.CASCADE)
    value = models.DecimalField(max_digits=10, decimal_places=2)
    base = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.0'))
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.0'))

    def __str__(self):
        return f"SalaryItemDetail for {self.salary.employee} - {self.salary.month}: {self.salary_item.name}"

    # def save(self, *args, **kwargs):


class Shift(models.Model):
    name = models.CharField(max_length=100)
    start_time = models.TimeField()
    end_time = models.TimeField()
    min_duration = models.DurationField(null=True, blank=True, default=timedelta)
    shift_factor = models.DecimalField(max_digits=10, decimal_places=2, default=1.0)

    def __str__(self):
        return self.name


# Queries model
class Query(models.Model):
    name = models.CharField(max_length=100, unique=True)
    type = models.PositiveSmallIntegerField(
            choices=[(1, 'Xpertpharm'), (0, 'Interne')], default=1)
    query = models.TextField()
    parameters = models.JSONField()
    help = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


# tasks
class TaskType(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Task(models.Model):
    task_name = models.CharField(max_length=50)
    task_description = models.CharField(max_length=200, blank=True, null=True)
    average_duration = models.DurationField(blank=True, null=True, default=timedelta)
    priority = models.PositiveSmallIntegerField(
        choices=[(1, 'Priorite 1'), (2, 'Priorite 2'), (3, 'Priorite 3'), (4, 'Priorite 4')], default=4)
    task_type = models.ForeignKey(TaskType, on_delete=models.CASCADE, null=True, blank=True)
    responsibility_level = models.ForeignKey(Rank, on_delete=models.CASCADE)
    repeat_freq = models.PositiveIntegerField(blank=True, null=True)  # Represents days
    progress_query = models.ForeignKey(Query, on_delete=models.PROTECT, null=True, blank=True)
    menu = models.BooleanField(default=False)
    transfer = models.BooleanField(default=False)

    def __str__(self):
        return self.task_name

    class Meta:
        ordering = ['id']


class Schedule(models.Model):
    STATUS_CHOICES = [
        (0, 'Planifié'),
        (1, 'En Cours'),
        (2, 'Non Clôturé'),
        (3, 'Clôturé'),
    ]
    date = models.DateField(null=True, blank=True)  # Initially allow null and blank
    start_time = models.TimeField()
    end_time = models.TimeField()
    schedule_name = models.CharField(max_length=255, null=True, blank=True)  # Initially allow null and blank
    is_template = models.BooleanField(default=False)
    schedule_status = models.IntegerField(choices=STATUS_CHOICES, default=0, db_index=True)

    @property
    def status_text(self):
        for value, text in self.STATUS_CHOICES:
            if value == self.schedule_status:
                return text

    def __str__(self):
        if self.is_template:
            return self.schedule_name
        else:
            return f"TRT:{self.status_text} {self.date}_{self.start_time}:{self.end_time}"

    def clean(self):
        errors = {}
        if not self.is_template and not self.date:
            errors['date'] = 'Date is required when is_template is False.'
        if self.is_template and not self.schedule_name:
            errors['schedule_name'] = 'Name is required when is_template is True.'
        if errors:
            raise ValidationError(errors)

    class Meta:
        # Enforce unique constraint on the combination of date, start_time, and end_time
        constraints = [
            models.UniqueConstraint(fields=['date', 'start_time', 'end_time'], name='unique_schedule_datetime')
        ]


class ScheduleEmployee(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE)
    working_hours = models.DurationField(blank=True, null=True, default=timedelta) # employee Working hours in schedule
    total_assigned_time = models.DurationField(blank=True, null=True, default=timedelta) # Total employee assigned time
    score = models.IntegerField(blank=True, null=True, default=0)

    def __str__(self):
        return f"{self.employee.first_name} - {self.schedule.date}"


class ScheduleTask(models.Model):
    STATUS_CHOICES = [
        (0, 'Not Started'),
        (1, 'In Progress'),
        (2, 'Completed'),
        (3, 'Overdue'),
        (4, 'Reported')
    ]

    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE)
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    total_time = models.DurationField(blank=True, null=True, default=timedelta)
    completion = models.IntegerField(blank=True, null=True, default=0)
    status = models.IntegerField(choices=STATUS_CHOICES, default=0, db_index=True)
    total_assigned_time = models.DurationField(blank=True, null=True, default=timedelta)

    def __str__(self):
        return f"{self.task.task_name} - {self.schedule.date}: {self.schedule.start_time} / {self.schedule.end_time}"


class ScheduleItem(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, blank=True, null=True)
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE)
    assigned_time = models.DurationField(default=timedelta)  # Time assigned to the employee for the task in the schedule
    progression_rate = models.IntegerField(blank=True, null=True, default=0)
    progress_lines = models.IntegerField(blank=True, null=True, default=0)
    task_identifier = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        if self.employee:
            return f"{self.employee.first_name} - {self.schedule.date} - {self.task.task_name}"
        else:
            return f"No Employee - {self.schedule.date} - {self.task.task_name}"


# Tasks Auto Generaion
class TaskGeneration(models.Model):
    name = models.CharField(max_length=50)
    parent_task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='generated_tasks')
    generated_task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='triggering_task')
    order = models.PositiveSmallIntegerField(default=1)

    def __str__(self):
        return f"{self.parent_task.task_name} generates {self.generated_task.task_name} (Order: {self.order})"


# Commandes models
# Reception1/5
class Reception(models.Model):
    supplier = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    number_of_packs = models.PositiveIntegerField()
    cold_chain = models.BooleanField(null=True, blank=True, default=None)
    psycho = models.BooleanField(null=True, blank=True, default=None)
    correct_destination = models.BooleanField(null=True, blank=True, default=None)
    products_type = models.BooleanField(null=True, blank=True, default=None)
    ref_tiers = models.CharField(max_length=50, blank=True, null=True, db_index=True)
    reception_date = models.DateField(auto_now_add=True, db_index=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    related_item = models.ForeignKey(ScheduleItem, on_delete=models.CASCADE, null=True, blank=True
                                     , related_name='related_details')

    @classmethod
    def get_form(cls):
        return f"{cls.__name__}Form"

    def __str__(self):
        return f"Reception_{self.supplier}#{self.ref_tiers}"

# Reception2/5 Saisie
class Saisie(models.Model):
    supplier = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    ref_tiers = models.CharField(max_length=50, blank=True, null=True, db_index=True)
    origine = models.ForeignKey(Reception, on_delete=models.CASCADE, null=True, blank=True)
    number_of_lines = models.PositiveIntegerField()
    employee1 = models.ForeignKey(Employee, related_name='invoices_employee1', on_delete=models.SET_NULL, null=True, blank=True)
    employee2 = models.ForeignKey(Employee, related_name='invoices_employee2', on_delete=models.SET_NULL, null=True, blank=True)
    employee3 = models.ForeignKey(Employee, related_name='invoices_employee3', on_delete=models.SET_NULL, null=True, blank=True)
    employee1_range_start = models.PositiveIntegerField(null=True, blank=True)
    employee1_range_end = models.PositiveIntegerField(null=True, blank=True)
    employee2_range_start = models.PositiveIntegerField(null=True, blank=True)
    employee2_range_end = models.PositiveIntegerField(null=True, blank=True)
    employee3_range_start = models.PositiveIntegerField(null=True, blank=True)
    employee3_range_end = models.PositiveIntegerField(null=True, blank=True)
    employee1_schedule_item = models.ForeignKey(ScheduleItem, related_name='related_details_1', on_delete=models.SET_NULL, null=True, blank=True)
    employee2_schedule_item = models.ForeignKey(ScheduleItem, related_name='related_details_2', on_delete=models.SET_NULL, null=True, blank=True)
    employee3_schedule_item = models.ForeignKey(ScheduleItem, related_name='related_details_3', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    # may be adding related items for each assignation

    @classmethod
    def get_form(cls):
        return f"{cls.__name__}Form"

    def __str__(self):
        return f"Saisie_{self.supplier}#{self.ref_tiers}"

# Reception3/5 Produit
class ReceptionProduit(models.Model):
    supplier = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    ref_tiers = models.CharField(max_length=50, blank=True, null=True, db_index=True)
    origine = models.ForeignKey(Saisie, on_delete=models.CASCADE, null=True, blank=True)
    number_of_lines = models.PositiveIntegerField()
    employee1 = models.ForeignKey(Employee, related_name='verification_employee1', on_delete=models.SET_NULL, null=True, blank=True)
    employee2 = models.ForeignKey(Employee, related_name='verification_employee2', on_delete=models.SET_NULL, null=True, blank=True)
    employee3 = models.ForeignKey(Employee, related_name='verification_employee3', on_delete=models.SET_NULL, null=True, blank=True)
    employee1_range_start = models.PositiveIntegerField(null=True, blank=True)
    employee1_range_end = models.PositiveIntegerField(null=True, blank=True)
    employee2_range_start = models.PositiveIntegerField(null=True, blank=True)
    employee2_range_end = models.PositiveIntegerField(null=True, blank=True)
    employee3_range_start = models.PositiveIntegerField(null=True, blank=True)
    employee3_range_end = models.PositiveIntegerField(null=True, blank=True)
    employee1_schedule_item = models.ForeignKey(ScheduleItem, related_name='related_verification_1', on_delete=models.SET_NULL, null=True, blank=True)
    employee2_schedule_item = models.ForeignKey(ScheduleItem, related_name='related_verification_2', on_delete=models.SET_NULL, null=True, blank=True)
    employee3_schedule_item = models.ForeignKey(ScheduleItem, related_name='related_verification_3', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    @classmethod
    def get_form(cls):
        return f"{cls.__name__}Form"

    def __str__(self):
        return f"ReceptionProduit_{self.supplier}#{self.ref_tiers}"

# Reception4/5 Vignette
class ReceptionVignette(models.Model):
    supplier = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    ref_tiers = models.CharField(max_length=50, blank=True, null=True, db_index=True)
    origine = models.ForeignKey(ReceptionProduit, on_delete=models.CASCADE, null=True, blank=True)
    number_of_lines = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    employee1 = models.ForeignKey(Employee, related_name='vignette_employee1', on_delete=models.SET_NULL, null=True, blank=True)
    employee2 = models.ForeignKey(Employee, related_name='vignette_employee2', on_delete=models.SET_NULL, null=True, blank=True)
    employee3 = models.ForeignKey(Employee, related_name='vignette_employee3', on_delete=models.SET_NULL, null=True, blank=True)
    employee1_range_start = models.PositiveIntegerField(null=True, blank=True)
    employee1_range_end = models.PositiveIntegerField(null=True, blank=True)
    employee2_range_start = models.PositiveIntegerField(null=True, blank=True)
    employee2_range_end = models.PositiveIntegerField(null=True, blank=True)
    employee3_range_start = models.PositiveIntegerField(null=True, blank=True)
    employee3_range_end = models.PositiveIntegerField(null=True, blank=True)
    employee1_schedule_item = models.ForeignKey(ScheduleItem, related_name='related_vignette_1', on_delete=models.SET_NULL, null=True, blank=True)
    employee2_schedule_item = models.ForeignKey(ScheduleItem, related_name='related_vignette_2', on_delete=models.SET_NULL, null=True, blank=True)
    employee3_schedule_item = models.ForeignKey(ScheduleItem, related_name='related_vignette_3', on_delete=models.SET_NULL, null=True, blank=True)

    # Related name for accessing employees
    # employees = models.ManyToManyField(Employee, through='CollageVignette', related_name='related_vignette')

    @classmethod
    def get_form(cls):
        return f"{cls.__name__}Form"

    def __str__(self):
        return f"ReceptionVignette_{self.supplier}#{self.ref_tiers}"


class ReceptionPlacement(models.Model):
    supplier = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    ref_tiers = models.CharField(max_length=50, blank=True, null=True, db_index=True)
    origine = models.ForeignKey(ReceptionVignette, on_delete=models.CASCADE, null=True, blank=True)
    number_of_lines = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    employee1 = models.ForeignKey(Employee, related_name='Placement_employee1', on_delete=models.SET_NULL, null=True, blank=True)
    employee2 = models.ForeignKey(Employee, related_name='Placement_employee2', on_delete=models.SET_NULL, null=True, blank=True)
    employee3 = models.ForeignKey(Employee, related_name='Placement_employee3', on_delete=models.SET_NULL, null=True, blank=True)
    employee1_range_start = models.PositiveIntegerField(null=True, blank=True)
    employee1_range_end = models.PositiveIntegerField(null=True, blank=True)
    employee2_range_start = models.PositiveIntegerField(null=True, blank=True)
    employee2_range_end = models.PositiveIntegerField(null=True, blank=True)
    employee3_range_start = models.PositiveIntegerField(null=True, blank=True)
    employee3_range_end = models.PositiveIntegerField(null=True, blank=True)
    employee1_schedule_item = models.ForeignKey(ScheduleItem, related_name='related_Placement_1', on_delete=models.SET_NULL, null=True, blank=True)
    employee2_schedule_item = models.ForeignKey(ScheduleItem, related_name='related_Placement_2', on_delete=models.SET_NULL, null=True, blank=True)
    employee3_schedule_item = models.ForeignKey(ScheduleItem, related_name='related_Placement_3', on_delete=models.SET_NULL, null=True, blank=True)

    @classmethod
    def get_form(cls):
        return f"{cls.__name__}Form"

    def __str__(self):
        return f"ReceptionPlacement_{self.supplier}#{self.ref_tiers}"


# Gestion des Stocks
# Operations stock
class StockOperation(models.Model):
    units = [
        ('Emp', 'Emplacement'),
        ('Prd', 'Produit'),
        ('Lot', 'Lot'),
        ('Bte', 'Boite')
    ]
    designation = models.CharField(max_length=50)
    duration = models.DurationField(default=timedelta)
    task = models.ForeignKey(Task, on_delete=models.SET_NULL, null=True, blank=True)
    # calculation = models.CharField(max_length=20, choices=units, default='Emp')

    def __str__(self):
        return f"{self.designation}"


# emplacement stock
class AssignationEmplacement(models.Model):
    emplacement = models.CharField(max_length=10, blank=True, null=True, db_index=True)
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True)
    operation = models.ForeignKey(StockOperation, on_delete=models.SET_NULL, null=True, blank=True)
    date_debut = models.DateField(null=True, blank=True, db_index=True)
    date_fin = models.DateField(null=True, blank=True, db_index=True)

    def clean(self):
        # Ensure end date is after start date
        if self.date_debut and self.date_fin:
            if self.date_fin < self.date_debut:
                raise ValidationError("End date must be after the start date.")
        # handeling ovelapping dates
        if self.date_debut and self.date_fin:
            existing_assignments = AssignationEmplacement.objects.filter(
                emplacement=self.emplacement,
                operation=self.operation
            ).exclude(pk=self.pk)  # Exclude the current instance

            for existing_assignment in existing_assignments:
                if (self.date_debut <= existing_assignment.date_fin and
                        self.date_fin >= existing_assignment.date_debut):
                    existing_assignment.date_fin = self.date_debut - timedelta(days=1)
                    existing_assignment.save()
        super().clean()

    def __str__(self):
        return f"{self.emplacement}_{self.employee}_{self.operation}"


# attendance terminal
class Terminal(models.Model):
    terminal_id = models.CharField(max_length=50, unique=True)
    ip_address = models.GenericIPAddressField()

    def __str__(self):
        return self.terminal_id


# xpert server
class XpertServer(models.Model):
    DRIVER_CHOICES = [
        ('ODBC Driver 17 for SQL Server', 'ODBC Driver 17 for SQL Server'),  # Fast
        ('ODBC Driver 18 for SQL Server', 'ODBC Driver 18 for SQL Server'), # Fast need certificate
        ('FreeTDS', 'FreeTDS'),
        ('SQL Server', 'SQL Server'),
    ]
    name = models.CharField(max_length=100, blank=True, null=True)
    servername = models.CharField(max_length=100)
    database = models.CharField(max_length=100)
    user = models.CharField(max_length=100)
    pwd = models.CharField(max_length=100)
    active = models.BooleanField(default=False)
    driver = models.CharField(max_length=100, choices=DRIVER_CHOICES, default='FreeTDS')

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.active:
            XpertServer.objects.exclude(id=self.id).update(active=False)

        super(XpertServer, self).save(*args, **kwargs)

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

class CustomUser(AbstractUser):
    pass
    # additional fields will be added here

    def __str__(self):
        return self.username

class Rank(models.Model):
    value = models.PositiveSmallIntegerField(unique=True)
    label = models.CharField(max_length=50)

    def __str__(self):
        return self.label


class Employee(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, null=True, blank=True)
    salary_items = models.ManyToManyField("ounissi_app.SalaryItem", blank=True)
    first_name = models.CharField(max_length=100, null=True, blank=True)
    last_name = models.CharField(max_length=100, null=True, blank=True, default='')
    birth_date = models.DateField(blank=True, default=None, null=True)
    recruiting_date = models.DateField(blank=True, default=None, null=True)
    social_number = models.CharField(max_length=20, null=True, blank=True)
    bank_account = models.CharField(max_length=40, null=True, blank=True)
    address = models.CharField(max_length=200, null=True, blank=True)
    position = models.CharField(max_length=100, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
    zk_id = models.CharField(max_length=50, null=True, blank=True, db_index=True)
    xp_id = models.CharField(max_length=50, null=True, blank=True, db_index=True)
    rank = models.ForeignKey(Rank, on_delete=models.SET_NULL, null=True, blank=True, default=4)

    # --- New Leave Management Fields ---
    leave_starting_balance = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        verbose_name="Solde de départ"
    )
    leave_starting_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Date de départ du solde",
        help_text="Date à partir de laquelle s'applique le solde initial. Si vide, utilise la date de recrutement."
    )
    leave_accrual_rate = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=2.50,
        verbose_name="Jours acquis par mois",
        help_text="Nombre de jours de congé accumulés par mois valide (ex: 2.5)."
    )
    min_working_days_for_accrual = models.PositiveSmallIntegerField(
        default=15,
        verbose_name="Jours minimum requis/mois",
        help_text="Nombre de jours de présence requis dans un mois pour obtenir le droit aux congés."
    )

    def calculate_leave_balance(self):
        """
        Dynamically calculates the leave balance for the employee.
        Accrues leave_accrual_rate for each completed calendar month where
        the employee has worked >= min_working_days_for_accrual.
        """
        # 1. Determine starting date
        start_date = self.leave_starting_date or self.recruiting_date
        if not start_date:
            return {
                'starting': 0.0, 'accrued': 0.0, 'taken': 0.0,
                'pending': 0.0, 'current': 0.0, 'available': 0.0
            }

        today = timezone.localtime().date()

        # 2. Generate list of fully completed months since start_date
        completed_months = []
        current_year = start_date.year
        current_month = start_date.month

        while True:
            # A calendar month is fully completed if we are in a later year, or same year but later month
            if (today.year > current_year) or (today.year == current_year and today.month > current_month):
                completed_months.append((current_year, current_month))
            else:
                break

            # Increment to next month
            if current_month == 12:
                current_month = 1
                current_year += 1
            else:
                current_month += 1

        # 3. Calculate accrued days based on valid completed months
        # Import Timesheet locally to avoid circular dependency
        from ounissi_app.models import Timesheet

        accrued_days = 0.0
        for y, m in completed_months:
            # Count validated working days in this specific month
            worked_days = Timesheet.objects.filter(
                employee=self,
                date__year=y,
                date__month=m,
                leave_type=Timesheet.LeaveType.NONE,
                is_confirmed=True
            ).count()

            if worked_days >= self.min_working_days_for_accrual:
                accrued_days += float(self.leave_accrual_rate)

        # 4. Count approved taken leaves (Confirmed, non-working days)
        taken_leaves = Timesheet.objects.filter(
            employee=self,
            date__gte=start_date,
            date__lte=today,
            is_confirmed=True
        ).exclude(leave_type=Timesheet.LeaveType.NONE).count()

        # 5. Count pending leave requests (Unconfirmed upcoming leave)
        pending_leaves = Timesheet.objects.filter(
            employee=self,
            date__gte=today,
            is_confirmed=False
        ).exclude(leave_type=Timesheet.LeaveType.NONE).count()

        # Computations
        current_balance = float(self.leave_starting_balance) + accrued_days - taken_leaves
        available_balance = current_balance - pending_leaves

        return {
            'starting': float(self.leave_starting_balance),
            'accrued': accrued_days,
            'taken': taken_leaves,
            'pending': pending_leaves,
            'current': current_balance,
            'available': available_balance
        }

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class Team(models.Model):
    name = models.CharField(max_length=50)
    employees = models.ManyToManyField(Employee, related_name='teams')
    leader = models.OneToOneField(Employee, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.name

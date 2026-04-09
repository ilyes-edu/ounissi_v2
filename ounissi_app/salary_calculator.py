from datetime import timedelta
from .models import Salary, SalaryItem, SalaryDetail, Timesheet
from accounts.models import Employee
import decimal


class SalaryCalculator:
    def __init__(self, employee, month):
        self.employee = employee
        self.month = month
        # self.timesheets = Timesheet.objects.filter(
        #     employee=employee, date__year=month.year, date__month=month.month
        # )

    def calculate_working_hours(self):
        salary_record, created = Salary.objects.get_or_create(employee=self.employee, month=self.month)
        timesheets = Timesheet.objects.filter(
            employee=self.employee, date__gte=salary_record.start_date, date__lte=salary_record.end_date
        )
        total_hours = timedelta()
        for timesheet in timesheets:
            total_hours += timedelta(hours=timesheet.calculate_working_hours())
        return total_hours

    def calculate_salary_items(self, item, value):
        # Create or get the salary record for this employee and month
        salary_record, created = Salary.objects.get_or_create(employee=self.employee, month=self.month)
        amount = 0
        base = 0
        # Calculate items with different CalculationTypes
        if item.calculation_type == 'fixed':
            # For FIXED items, return the provided value
            amount = value
        elif item.calculation_type == 'multiply_hours':
            # For MULTIPLY_HOURS items, multiply the provided value by working hours
            total_hours = self.calculate_working_hours().total_seconds() / 3600
            base = decimal.Decimal(total_hours)
            amount = value * base
        else:
            # For items related to other items, perform an arithmetic operation
            dependent_item = item.dependent_item
            if dependent_item:
                if item.calculation_type == SalaryItem.CalculationType.PERCENTAGE:
                    # Calculate as a percentage of the dependent item
                    base = self.calculate_salary_items(dependent_item, 1).amount
                    amount = value * base
                elif item.calculation_type == SalaryItem.CalculationType.ADDITION:
                    # Calculate as an addition of the dependent item
                    base = self.calculate_salary_items(dependent_item, 0).amount
                    amount = value + base
                # You can add other cases for different CalculationTypes here
            else:
                amount = 0.0  # If there's no dependent item, return the provided value
                base = 0.0

        # Create or update SalaryItemDetail records
        detail, created = SalaryDetail.objects.get_or_create(
            salary=salary_record,
            salary_item=item,
        )
        detail.amount = amount
        detail.base = base
        detail.save()

        # Optionally, return the calculated item or value
        return detail

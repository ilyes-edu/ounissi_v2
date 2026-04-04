from datetime import datetime, timedelta
from .models import Task, Employee, ScheduleTask, ScheduleEmployee, ScheduleItem
from .forms import ScheduleItemForm
from django.forms import formset_factory



# method to create schedule
def create_schedule_items(schedule, tasks_with_durations, employees_with_working_hours):
    schedule_item_forms = []

    for task, duration in tasks_with_durations.items():
        schedule_task = ScheduleTask.objects.create(schedule=schedule, task=task)
        remaining_time = schedule_task.remaining_time

        eligible_employees = [employee for employee in employees_with_working_hours if employee.rank >= task.responsibility_level]

        # Distribute tasks evenly among eligible employees, considering remaining time
        per_employee_time = min(duration, remaining_time // len(eligible_employees))

        for employee in eligible_employees:
            schedule_employee = ScheduleEmployee.objects.get(schedule=schedule, employee=employee)
            remaining_hours = schedule_employee.remaining_hours

            allocated_time = min(per_employee_time, remaining_hours)

            if allocated_time > 0:
                schedule_item = ScheduleItem.objects.create(
                    schedule=schedule,
                    employee=employee,
                    task=task,
                    assigned_time=allocated_time,
                    progression_rate=0
                )
                schedule_items.append(schedule_item)

                # Update remaining times
                schedule_employee.remaining_hours -= allocated_time
                schedule_employee.save()
                schedule_task.remaining_time -= allocated_time
                schedule_task.save()

    return schedule_items


def distribute_tasks_helper(tasks_with_durations, employees_with_working_hours):
    schedule_item_forms = []

    for task_data in tasks_with_durations:
        task = Task.objects.get(pk=task_data['task_id'])
        duration = task_data['total_duration']
        eligible_employees = [
            employee_data for employee_data in employees_with_working_hours
            if int(employee_data['employee_rank']) <= task.responsibility_level.value
        ]

        while duration > timedelta(0) and eligible_employees:
            temporary_assignments = []  # Initialize temporary list
            per_employee_duration = duration / len(eligible_employees)

            for employee_data in eligible_employees:
                employee_instance = Employee.objects.get(pk=employee_data['employee_id'])
                assigned_time = min(per_employee_duration, employee_data['working_hours'])

                schedule_item_form = ScheduleItemForm({
                    'task_id': task.id,
                    'task_name': task.task_name,
                    'employee_id': employee_instance.id,
                    'employee_name': employee_instance.first_name,
                    'assigned_time': assigned_time,
                })

                temporary_assignments.append(schedule_item_form)

                # Check for incomplete assignment
                if employee_data['working_hours'] < per_employee_duration:
                    schedule_item_forms.append(schedule_item_form)  # Append the existing form
                    employee_data['working_hours'] -= assigned_time
                    eligible_employees = [
                        employee_data for employee_data in eligible_employees
                        if employee_data['working_hours'] > timedelta(0)
                    ]
                    if eligible_employees:
                        per_employee_duration = duration / len(eligible_employees)
                    break  # Re-enter the loop for reassignment

            if temporary_assignments:
                schedule_item_forms.extend(temporary_assignments)  # Finalize assignments

    return schedule_item_forms

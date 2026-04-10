from django import template
from datetime import timedelta

register = template.Library()

@register.filter(name='hours_minutes')
def hours_minutes(value):
    """
    Converts a timedelta or integer minutes into a HH:MM string.
    """
    if not value:
        return "00:00"

    # If it's a timedelta (which our new view sends)
    if isinstance(value, timedelta):
        total_seconds = int(value.total_seconds())
        # Handle negative timedeltas if they exist
        abs_seconds = abs(total_seconds)
        hours = abs_seconds // 3600
        minutes = (abs_seconds % 3600) // 60
        return f"{'-' if total_seconds < 0 else ''}{hours:02d}:{minutes:02d}"

    # Fallback if it's still receiving an integer (old logic)
    try:
        total_minutes = int(value)
        hours = total_minutes // 60
        minutes = total_minutes % 60
        return f"{hours:02d}:{minutes:02d}"
    except (ValueError, TypeError):
        return "00:00"

@register.filter(name='model_fields')
def get_model_fields(queryset):
    return queryset.model._meta.get_fields()

@register.filter
def division(value, divisor):
    """
    Custom template filter to perform division.
    """
    try:
        return value // divisor
    except (TypeError, ZeroDivisionError):
        return value

@register.filter
def multiplication(value, multiplier):
    return value * multiplier

@register.filter
def substruction(value1, value2):
    return value1 - value2

@register.filter
def addition(value1, value2):
    return value1 + value2

@register.filter
def div(value, divisor):
    """
    Custom template filter to perform division.
    """
    try:
        return value / divisor
    except (TypeError, ZeroDivisionError):
        return value


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key, [])

@register.filter
def get_assignments_for_employee(assignments, employee_id):
    return [assignment for assignment in assignments if assignment.employee.id == employee_id]

@register.filter
def get_assignment_for_operation(assignments, operation_id):
    return next((assignment for assignment in assignments if assignment.operation.id == operation_id), None)

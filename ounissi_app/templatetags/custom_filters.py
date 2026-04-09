from django import template

register = template.Library()

@register.filter(name='hours_minutes')
def hours_minutes(value):
    hours, minutes = divmod(int(value * 60), 60)
    return f'{hours:02d}:{minutes:02d}'

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

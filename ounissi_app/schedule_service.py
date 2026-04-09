from datetime import timedelta
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.apps import apps
from django.db import connection
from django.db.models import Sum, F, FloatField
from django.db.models.functions import Cast
from accounts.models import Employee
from .models import Schedule, ScheduleItem, ScheduleTask, ScheduleEmployee, TaskGeneration, Task, User
from .xpertcon import XpertConnect

import logging

logger = logging.getLogger(__name__)


def update_all_schedule_statuses():
    """
    Updates the status of all schedules based on the current date and time.
    0 = Planifié, 1 = En Cours, 2 = Non Clôturé, 3 = Clôturé
    """
    now = timezone.localtime()
    today = now.date()
    current_time = now.time()
    limit_date = today - timedelta(days=30)

    # 1. Set older than 30 days to Clôturé (3)
    Schedule.objects.filter(is_template=False, date__lt=limit_date).exclude(schedule_status=3).update(schedule_status=3)

    # 2. Set past schedules (but newer than 30 days) to Non Clôturé (2)
    Schedule.objects.filter(is_template=False, date__lt=today, date__gte=limit_date).exclude(schedule_status=3).update(
        schedule_status=2)

    # 3. Handle Today's schedules
    today_schedules = Schedule.objects.filter(is_template=False, date=today).exclude(schedule_status=3)
    for sched in today_schedules:
        if current_time < sched.start_time:
            new_status = 0  # Planifié
        elif sched.start_time <= current_time <= sched.end_time:
            new_status = 1  # En Cours
        else:
            new_status = 2  # Non Clôturé (Ended today)

        if sched.schedule_status != new_status:
            sched.schedule_status = new_status
            sched.save(update_fields=['schedule_status'])


def get_current_active_schedule():
    """Returns the currently active schedule for today, or None."""
    update_all_schedule_statuses()
    now = timezone.localtime()
    return Schedule.objects.filter(
        is_template=False,
        date=now.date(),
        start_time__lte=now.time(),
        end_time__gte=now.time()
    ).first()


def get_schedule_context_data(schedule, employee=None):
    """
    Fetches all related items, tasks, and employees for a given schedule.
    If employee is provided, filters items for that specific employee.
    """
    if not schedule:
        return None

    context = {
        'schedule': schedule,
        'schedule_employees': ScheduleEmployee.objects.filter(schedule=schedule),
        'schedule_tasks': ScheduleTask.objects.filter(schedule=schedule),
    }

    if employee:
        context['schedule_items'] = ScheduleItem.objects.filter(schedule=schedule, employee=employee)
    else:
        context['schedule_items'] = ScheduleItem.objects.filter(schedule=schedule, employee__isnull=False)

    # Logic for unassigned/ready items
    no_employee_items = ScheduleItem.objects.filter(schedule=schedule, employee__isnull=True)
    non_assigned_items = []

    for item in no_employee_items:
        original_item = get_original_item(item)
        if original_item:
            ready = True
            upper_items = ScheduleItem.objects.filter(
                schedule=schedule,
                task=original_item.task,
                task_identifier__contains=original_item.task_identifier.split('Lines')[0]
            )
            for upper_item in upper_items:
                if upper_item.progression_rate < 100:
                    ready = False

            if ready:
                non_assigned_items.append(item)

    context['non_assigned_items'] = non_assigned_items
    return context


# --- PROGRESS CALCULATION LOGIC ---

def run_raw_query(query_obj, parameters):
    """Helper to run queries and return dict (replaces old Pandas logic)"""
    try:
        if query_obj.type == 0:  # Internal SQLite
            with connection.cursor() as cursor:
                cursor.execute(query_obj.query, parameters)
                results = cursor.fetchall()
                columns = [col[0] for col in cursor.description]
                data_rows = [tuple(row) for row in results]
                return {'columns': columns, 'data_rows': data_rows}
        else:  # Xpertpharm
            conn = XpertConnect()
            conn.open_session()
            res = conn.run_query(query_obj.query, parameters)
            conn.close_session()
            return res
    except Exception as e:
        logger.error(f"Query Error: {e}")
        return None


def get_item_progress(item_id):
    """Calculates progress for a single ScheduleItem using the new raw dict format."""
    schedule_item = ScheduleItem.objects.select_related('employee', 'schedule', 'task__progress_query').get(pk=item_id)

    if not schedule_item.task.progress_query:
        return

    xp_id = schedule_item.employee.xp_id
    parameters = {
        "start_date": schedule_item.schedule.date,
        "end_date": schedule_item.schedule.date + timedelta(days=1),
        "xp_id": xp_id
    }

    if schedule_item.task_identifier:
        try:
            model_name = schedule_item.task.progress_query.parameters.get('model_name')
            if model_name:
                model = apps.get_model('ounissi_app', model_name)
                items = get_related_item_details(schedule_item, model)
                if items:
                    parameters['supplier'] = items[0].supplier
                    parameters['ref_tiers'] = items[0].ref_tiers
        except Exception as ex:
            logger.error(f"Progress Params Exception: {ex}")

    results = run_raw_query(schedule_item.task.progress_query, parameters)

    if results and len(results['data_rows']) > 0:
        try:
            # Find the index of NBR_LINES safely
            col_idx = results['columns'].index('NBR_LINES')
            nbr_lines = results['data_rows'][0][col_idx]

            if nbr_lines:
                schedule_item.progress_lines = int(nbr_lines)
                # Calculate assigned duration in seconds
                assigned_sec = schedule_item.assigned_time.total_seconds()
                task_sec = schedule_item.task.average_duration.total_seconds()

                auto_progress_sec = nbr_lines * task_sec
                if assigned_sec > 0:
                    schedule_item.progression_rate = int((auto_progress_sec / assigned_sec) * 100)
                schedule_item.save(update_fields=['progress_lines', 'progression_rate'])
        except ValueError:
            logger.warning("NBR_LINES not found in query results.")
        except Exception as ex:
            logger.error(f"Progress calculation error: {ex}")


#
# def update_schedule_progress(schedule, employee=None):
#     """Updates progress for all items in a schedule using a single DB connection."""
#
#     if employee:
#         schedule_items = ScheduleItem.objects.filter(schedule=schedule, employee=employee).select_related(
#             'task__progress_query', 'employee')
#     else:
#         schedule_items = ScheduleItem.objects.filter(schedule=schedule, employee__isnull=False).select_related(
#             'task__progress_query', 'employee')
#
#     # 1. OPEN A SINGLE XPERTPHARM CONNECTION FOR THE ENTIRE LOOP
#     conn = XpertConnect()
#     try:
#         conn.open_session()
#
#         # 2. Process all items using the active connection
#         for item in schedule_items:
#             if item.task.progress_query and item.task.progress_query.query != 'N/A':
#                 # We pass the active connection directly to a modified progress function
#                 _calculate_item_progress_with_conn(item, conn)
#
#     finally:
#         # 3. ENSURE THE CONNECTION CLOSES EVEN IF AN ERROR OCCURS
#         conn.close_session()
#
#     # 4. OPTIMIZE EMPLOYEE SCORES (No more Python looping, let the Database do the math)
#     # This replaces your python "sum(... for i in ...)" loop with a single lightning-fast database query
#     sched_emps = ScheduleEmployee.objects.filter(schedule=schedule)
#     for sched_emp in sched_emps:
#         # Calculate score: SUM(progress_lines / task.priority)
#         total_score = ScheduleItem.objects.filter(
#             employee=sched_emp.employee,
#             schedule=schedule,
#             task__priority__gt=0
#         ).aggregate(
#             score=Sum(Cast('progress_lines', FloatField()) / Cast('task__priority', FloatField()))
#         )['score'] or 0
#
#         sched_emp.score = total_score
#         sched_emp.save(update_fields=['score'])
#
#     # 5. OPTIMIZE TASK COMPLETION
#     for sched_task in ScheduleTask.objects.filter(schedule=schedule):
#         total_sec = sched_task.total_assigned_time.total_seconds()
#         if total_sec > 0:
#             # Aggregate the completed seconds directly in the database
#             completion_sec = ScheduleItem.objects.filter(
#                 task=sched_task.task,
#                 schedule=schedule
#             ).aggregate(
#                 completed=Sum((F('progression_rate') / 100.0) * F('assigned_time'))
#             )['completed']
#
#             # Extract total seconds from the timedelta if it exists
#             completion_sec_val = completion_sec.total_seconds() if completion_sec else 0
#
#             sched_task.completion = int((completion_sec_val / total_sec) * 100)
#             if sched_task.completion >= 100:
#                 sched_task.status = 2
#             sched_task.save(update_fields=['completion', 'status'])
#         else:
#             sched_task.delete()


def update_schedule_progress(schedule, employee=None):
    """Updates progress for all items in a schedule."""
    if employee:
        schedule_items = ScheduleItem.objects.filter(schedule=schedule, employee=employee)
    else:
        schedule_items = ScheduleItem.objects.filter(schedule=schedule, employee__isnull=False)

    for item in schedule_items:
        if item.task.progress_query and item.task.progress_query.query != 'N/A':
            get_item_progress(item.id)

    # Updating employees scores
    for sched_emp in ScheduleEmployee.objects.filter(schedule=schedule):
        score = sum(i.progress_lines / i.task.priority for i in
                    ScheduleItem.objects.filter(employee=sched_emp.employee, schedule=schedule) if i.task.priority)
        sched_emp.score = score
        sched_emp.save(update_fields=['score'])

    # Updating Tasks Completion
    for sched_task in ScheduleTask.objects.filter(schedule=schedule):
        completion_sec = sum((i.progression_rate / 100) * i.assigned_time.total_seconds() for i in
                             ScheduleItem.objects.filter(task=sched_task.task, schedule=schedule))
        total_sec = sched_task.total_assigned_time.total_seconds()

        if total_sec > 0:
            sched_task.completion = int((completion_sec / total_sec) * 100)
            if sched_task.completion >= 100:
                sched_task.status = 2
            sched_task.save(update_fields=['completion', 'status'])
        else:
            sched_task.delete()


# --- UTILITY HELPERS ---

def get_original_item(item):
    try:
        generation = TaskGeneration.objects.filter(generated_task=item.task).first()
        if generation:
            task_identifier = item.task_identifier.split('Lines')[0] if item.task_identifier else ""
            return ScheduleItem.objects.filter(task=generation.parent_task,
                                               task_identifier__contains=task_identifier).first()
    except Exception as ex:
        logger.error(f'Error getting original item: {ex}')
    return None


def get_related_item_details(schedule_item, model):
    related_objects = []
    for field in model._meta.get_fields():
        if field.is_relation and field.related_model == ScheduleItem:
            filter_kwargs = {field.name: schedule_item}
            related_objects.extend(model.objects.filter(**filter_kwargs))
    return related_objects


def update_schedule_from_item(task_id, assigned_time, schedule_id, employee_id=None, task_identifier=None,
                              progression_rate=None, item_id=None):
    # (Your existing logic, just moved here to keep views clean)
    existing_item = None
    if item_id:
        existing_item = get_object_or_404(ScheduleItem, pk=item_id)
    elif employee_id and task_id and schedule_id:
        query = {'employee_id': employee_id, 'task_id': task_id, 'schedule_id': schedule_id}
        if task_identifier:
            query['task_identifier'] = task_identifier
        existing_item = ScheduleItem.objects.filter(**query).first()

    if existing_item:
        schedule_item = existing_item
        assigned_delta = assigned_time - schedule_item.assigned_time
    else:
        schedule_item = ScheduleItem(task_id=task_id, schedule_id=schedule_id, progression_rate=0)
        assigned_delta = assigned_time

    if assigned_time: schedule_item.assigned_time = assigned_time
    if employee_id: schedule_item.employee_id = employee_id
    if task_identifier: schedule_item.task_identifier = task_identifier
    if progression_rate is not None: schedule_item.progression_rate = progression_rate

    schedule_item.save()
    return schedule_item, assigned_delta


def update_employee_task_from_item(schedule_item, assigned_delta):
    schedule = schedule_item.schedule
    employee = schedule_item.employee

    sched_emp, created = ScheduleEmployee.objects.get_or_create(
        employee=employee, schedule=schedule,
        defaults={'total_assigned_time': schedule_item.assigned_time}
    )
    if not created:
        sched_emp.total_assigned_time += assigned_delta
        sched_emp.save()

    sched_task, created = ScheduleTask.objects.get_or_create(
        task=schedule_item.task, schedule=schedule,
        defaults={'total_time': schedule_item.assigned_time, 'total_assigned_time': schedule_item.assigned_time}
    )
    if not created:
        sched_task.total_assigned_time += assigned_delta
        sched_task.save()


def generate_group_task(schedule_item, schedule):
    try:
        generation = TaskGeneration.objects.filter(parent_task=schedule_item.task).first()
        if generation:
            ScheduleItem.objects.create(
                schedule=schedule,
                task=generation.generated_task,
                task_identifier=schedule_item.task_identifier
            )
            return True
    except Exception as ex:
        logger.error(f"Generation Error: {ex}")
    return False
import json
# import time
from datetime import datetime, timedelta, time
from django.apps import apps
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.module_loading import import_string
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from django.db import IntegrityError, connection
import pandas as pd

from .models import *
from .forms import *
from accounts.models import Employee, Team
from .attendance_importer import import_attendance_logs, timesheet_dataframe, save_logs
from .xpertcon import XpertConnect
from .salary_calculator import SalaryCalculator
from .utils import getLoggedData
from .decorators import with_logged_data

# Import the new service layer
from . import schedule_service


@login_required
def timesheet_list(request):
    filter_form = TimesheetFilterForm(request.GET)

    # 1. Date boundaries
    today = timezone.localtime().date()
    start_date = today.replace(day=1)
    end_date = today

    timesheets = Timesheet.objects.select_related('employee').all()
    specific_xp_id = '%%'

    if filter_form.is_valid():
        f_start = filter_form.cleaned_data.get('start_date')
        f_end = filter_form.cleaned_data.get('end_date')
        f_employees = filter_form.cleaned_data.get('employees')

        if f_start: start_date = f_start
        if f_end: end_date = f_end

        timesheets = timesheets.filter(date__gte=start_date, date__lte=end_date)

        if f_employees:
            if isinstance(f_employees, Employee):
                f_employees = [f_employees]
                specific_xp_id = f_employees[0].xp_id or '%%'
            elif hasattr(f_employees, 'count') and f_employees.count() == 1:
                specific_xp_id = f_employees.first().xp_id or '%%'
            timesheets = timesheets.filter(employee__in=f_employees)
    else:
        timesheets = timesheets.filter(date__gte=start_date)

    timesheets = timesheets.order_by('employee', 'date')

    # 2. XpertPharm Audit Fetch
    xpert_logs_map = {}
    if timesheets.exists():
        query_str = """
                    SELECT CAST(CREATED_ON AS DATE)         AS OP_DATE,
                           CREATED_BY                       AS OP_USER,
                           CAST(MIN(CREATED_ON) AS TIME(0)) AS FIRST_LOG,
                           CAST(MAX(CREATED_ON) AS TIME(0)) AS LAST_LOG
                    FROM SYS_OBJET_TRACE WITH (NOLOCK)
                    WHERE CREATED_ON >= :start_date
                      AND CREATED_ON \
                        < :end_date
                      AND (:xp_id = '%%' \
                       OR CREATED_BY = :xp_id)
                    GROUP BY CREATED_BY, CAST (CREATED_ON AS DATE)
                    OPTION (RECOMPILE);
                    """
        params = {
            'start_date': start_date,
            'end_date': end_date + timedelta(days=1),
            'xp_id': specific_xp_id
        }

        try:
            results = XpertConnect().run_query(query_str, params)
            for row in results.get('data_rows', []):
                key = (str(row[1]), str(row[0]))
                xpert_logs_map[key] = {'first': row[2], 'last': row[3]}
        except Exception as e:
            print(f"XpertPharm Log Fetch Failed: {e}")

    # 3. Data Assembly
    timesheets_with_hours = []
    for ts in timesheets:
        raw_hours = ts.calculate_working_hours() or 0
        bio_hours = timedelta(hours=float(raw_hours))
        log = xpert_logs_map.get((str(ts.employee.xp_id), str(ts.date)), {'first': '--', 'last': '--'})

        xp_total_str = "--"
        warning = False

        if log['first'] != '--' and log['last'] != '--':
            try:
                # We use 'time' (the type we just imported) for the check
                t1_val = log['first']
                t2_val = log['last']

                # Convert to time objects if they aren't already
                t1_obj = t1_val if isinstance(t1_val, time) else datetime.strptime(str(t1_val), '%H:%M:%S').time()
                t2_obj = t2_val if isinstance(t2_val, time) else datetime.strptime(str(t2_val), '%H:%M:%S').time()

                # Combine with a dummy date to allow subtraction
                today = datetime.today()
                dt1 = datetime.combine(today, t1_obj)
                dt2 = datetime.combine(today, t2_obj)

                xp_delta = dt2 - dt1
                total_seconds = int(xp_delta.total_seconds())

                if total_seconds > 0:
                    h, remainder = divmod(total_seconds, 3600)
                    m, _ = divmod(remainder, 60)
                    xp_total_str = f"{h:02d}:{m:02d}"

                # --- WARNING LOGIC ---
                if xp_delta > (bio_hours + timedelta(minutes=5)):
                    warning = True
                elif bio_hours.total_seconds() == 0 and total_seconds > 300:
                    warning = True

            except Exception as e:
                print(f"DEBUG Error for {ts.employee}: {e}")

        # Missing Logout Check
        if (ts.start_time and not ts.end_time) or \
                (ts.start_time_2 and not ts.end_time_2) or \
                (ts.start_time_3 and not ts.end_time_3):
            warning = True

        timesheets_with_hours.append({
            'obj': ts,
            'hours': bio_hours,
            'xp_first': log['first'],
            'xp_last': log['last'],
            'xp_total': xp_total_str,
            'warning': warning
        })

    # 4. Define the context before returning
    context = {
        'filter_form': filter_form,
        'timesheets_with_hours': timesheets_with_hours,
        'logged_data': getLoggedData(request) if 'getLoggedData' in globals() else None
    }

    return render(request, 'timesheet/timesheet_list.html', context)


@login_required
def timesheet_create(request):
    if request.method == 'POST':
        form = TimesheetForm(request.POST)
        if form.is_valid():
            timesheet = form.save(commit=False)
            employee_id = form.cleaned_data['employee']
            employee = Employee.objects.get(id=employee_id)
            timesheet.employee = employee
            timesheet.save()
            return redirect('timesheet_list')
    else:
        form = TimesheetForm()
    return render(request, 'timesheet/timesheet_create.html', {'form': form})


@login_required
def timesheet_update(request, pk):
    timesheet = get_object_or_404(Timesheet, pk=pk)
    if request.method == 'POST':
        form = TimesheetForm(request.POST, instance=timesheet)
        if form.is_valid():
            form.save()
            return redirect('timesheet_list')
        else:
            form = TimesheetForm(instance=timesheet)
            return render(request, 'timesheet/update_timesheet.html', {'form': form})


@login_required
def timesheet_delete(request, pk):
    timesheet = get_object_or_404(Timesheet, pk=pk)
    if request.method == 'POST':
        timesheet.delete()
        return redirect('timesheet_list')
    return render(request, 'timesheet/timesheet_delete.html', {'timesheet': timesheet})


@login_required
def timesheet_form(request):
    if request.method == 'POST':
        form = TimesheetForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('timesheet_list')
    else:
        form = TimesheetForm()
    return render(request, 'timesheet/timesheet_form.html', {'form': form})


@login_required
def attendance_logs(request):
    if request.method == 'GET':
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        zk_id = request.GET.get('employee')
        all_logs = []

        # Calculate the 1st day of the current month
        today = timezone.localtime().date()
        first_day_current_month = today.replace(day=1)

        parsed_start_date = parse_date(start_date) if start_date else first_day_current_month
        parsed_end_date = parse_date(end_date) if end_date else today

        terminals = Terminal.objects.all()

        for terminal in terminals:
            # Collect logs from ALL terminals instead of overwriting
            device_logs = import_attendance_logs(device=terminal.ip_address)
            if device_logs:
                all_logs.extend(device_logs)

        logs = all_logs

        if zk_id:
            filtered_logs = [log for log in logs if
                             parsed_start_date <= log.timestamp.date() <= parsed_end_date and str(log.user_id) == str(
                                 zk_id)]
        else:
            filtered_logs = [log for log in logs if parsed_start_date <= log.timestamp.date() <= parsed_end_date]

        employees = Employee.objects.all()
        connection_status = True if logs else False

        if connection_status:
            attendance_df = timesheet_dataframe(filtered_logs)
            jsondata = attendance_df.reset_index().to_json(orient='records')
            data = json.loads(jsondata)
        else:
            data = []

        context = {'data': data,
                   'employees': employees,
                   'connection_status': connection_status,
                   'start_date': start_date,
                   'end_date': end_date,
                   'terminals': terminals,
                   'selected_employee': zk_id,
                   'logged_data': getLoggedData(request)}
        return render(request, 'timesheet/attendance_logs.html', context)


@login_required
def save_data(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        save_df = timesheet_dataframe(import_attendance_logs())
        save_df = save_df[save_df['employee_name'] != 'inexistant']

        if data['start_date']:
            save_df = save_df[parse_date(data['start_date']) <= save_df['date']]
        if data['end_date']:
            save_df = save_df[parse_date(data['end_date']) >= save_df['date']]
        if data['employee']:
            save_df = save_df[data['employee'] == save_df['user_id']]

        save_logs(save_df)
        return JsonResponse({'message': 'Data saved successfully'})

    return JsonResponse({'error': 'Invalid request method'})


@login_required
def salary_item_list(request):
    salary_items = SalaryItem.objects.all()
    context = {'salary_items': salary_items,
               'logged_data': getLoggedData(request)}
    return render(request, 'salary/salary_item_list.html', context)


@login_required
def salary_item_create(request):
    if request.method == 'POST':
        form = SalaryItemForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('salary_item_list')
    else:
        form = SalaryItemForm()
    return render(request, 'salary/salary_item_create.html', {'form': form})


@login_required
def salary_item_update(request, pk):
    salary_item = get_object_or_404(SalaryItem, pk=pk)
    if request.method == 'POST':
        form = SalaryItemForm(request.POST, instance=salary_item)
        if form.is_valid():
            form.save()
            return redirect('salary_item_list')
    else:
        form = SalaryItemForm(instance=salary_item)
    return render(request, 'salary/salary_item_update.html', {'form': form})


@login_required
def salary_item_delete(request, pk):
    salary_item = get_object_or_404(SalaryItem, pk=pk)
    if request.method == 'POST':
        salary_item.delete()
        return redirect('salary_item_list')
    return render(request, 'salary/salary_item_delete.html', {'salary_item': salary_item})


@login_required
def testconn(request):
    context = {'logged_data': getLoggedData(request)}
    return render(request, 'home.html', context)


@login_required
def test_query_submission(request):
    if request.method == 'POST':
        query_text = request.POST.get('queryText')
        parameters = get_dynamic_parameter(request)
        query_type = request.POST.get('type')
        temp_query = Query(
            name='temp',
            type=query_type,
            query=query_text,
            parameters=parameters
        )

        query_results = get_query_results(temp_query, parameters)
        context = {'query_results': query_results,
                   'logged_data': getLoggedData(request)}
        return render(request, 'queries/query_result.html', context)
    return render(request, 'queries/query_result.html', {'error_message': 'Invalid form'})


@login_required
def get_query_details(request, query_id):
    query = get_object_or_404(Query, pk=query_id)
    parameters = [{'name': key, 'value': value} for key, value in query.parameters.items() if key != 'model_name']
    return JsonResponse({'parameters': parameters})


@login_required
def execute_query(request):
    if request.method == 'POST':
        conn = None
        query_id = request.POST.get('query')
        query = get_object_or_404(Query, pk=query_id)
        parameters = query.parameters.copy()

        for key in parameters.keys():
            param = request.POST.get(key)
            if param:
                parameters[key] = param

        try:
            if query.type == 0:
                with connection.cursor() as cursor:
                    cursor.execute(query.query, parameters)
                    results = cursor.fetchall()
                    columns = [col[0] for col in cursor.description]

                data_rows = []
                op_user_index = columns.index('OP_USER') if 'OP_USER' in columns else -1

                for row in results:
                    row_list = list(row)
                    if op_user_index != -1:
                        try:
                            user_id = row_list[op_user_index]
                            xp_id = User.objects.get(pk=user_id).employee.xp_id
                            row_list[op_user_index] = xp_id
                        except Exception:
                            pass
                    data_rows.append(tuple(row_list))

                query_results = {'columns': columns, 'data_rows': data_rows}

            else:
                conn = XpertConnect()
                conn.open_session()
                query_results = conn.run_query(query.query, parameters)

            return render(request, 'queries/query_result.html', {'query_results': query_results})

        except (ValueError, ConnectionError, Exception) as ex:
            return render(request, 'queries/query_result.html',
                          {'error_message': f"Error executing the query: {str(ex)}"})
        finally:
            if query.type != 0 and conn:
                conn.close_session()

    return render(request, 'queries/query_result.html', {'error_message': "Invalid request"})


@login_required
def get_dynamic_parameter(request):
    parameters = {}
    for key, value in request.POST.items():
        if key.startswith('parameter') and value:
            param_name = value
            param_value = request.POST.get(f'value_{key}', '')
            parameters[param_name] = param_value
    return parameters


@login_required
def create_query(request):
    if request.method == 'POST':
        query_name = request.POST.get('queryName')
        query_text = request.POST.get('queryText')
        query_type = request.POST.get('type')
        parameters = get_dynamic_parameter(request)

        try:
            Query.objects.create(
                name=query_name,
                query=query_text,
                parameters=parameters,
                type=query_type
            )
            return redirect('test_queries')

        except IntegrityError:
            error_message = "A query with this name already exists. Please choose a different name."
            return render(request, 'queries/create_query.html', {'error_message': error_message})

    context = {'logged_data': getLoggedData(request)}
    return render(request, 'queries/create_query.html', context)


@login_required
def test_queries(request):
    queries = Query.objects.all()
    context = {'queries': queries,
               'logged_data': getLoggedData(request)}
    return render(request, 'queries/test_queries.html', context)


@login_required
def queries_list(request):
    queries = Query.objects.all()
    context = {'queries': queries,
               'logged_data': getLoggedData(request)}
    return render(request, 'queries/queries_list.html', context)


@login_required
def salary_list(request):
    employees = Employee.objects.all().order_by('last_name')
    salaries = Salary.objects.all().order_by('employee', 'month')

    if request.method == 'GET':
        employee = request.GET.get('employee')
        month = request.GET.get('month')

        if employee:
            salaries = salaries.filter(employee=employee)
        if month:
            try:
                month = datetime.strptime(month, '%Y-%m')
                month = month.replace(day=1)
            except ValueError:
                month = None
            salaries = salaries.filter(month=month)

    context = {
        'employees': employees,
        'salaries': salaries,
        'logged_data': getLoggedData(request)
    }
    return render(request, 'salary/salary_list.html', context)


@login_required
def get_salary_details(request, salary_id):
    salary = get_object_or_404(Salary, pk=salary_id)
    formset = SalaryDetailFormSet(queryset=SalaryDetail.objects.filter(salary=salary))

    context = {
        'salary': salary,
        'formset': formset,
        'logged_data': getLoggedData(request)
    }
    return render(request, 'salary/salary_detail_list.html', context)


@login_required
def create_or_update_salary(employee, month):
    salary, created = Salary.objects.get_or_create(employee=employee, month=month)
    formset = SalaryDetailFormSet(
        queryset=SalaryDetail.objects.filter(salary=salary),
        prefix='salarydetails'
    )
    return salary, formset


@login_required
def add_update_salary(request):
    employees = Employee.objects.all()

    if request.method == 'POST':
        employee_id = request.POST.get('employee')
        month = request.POST.get('month')
        employee = Employee.objects.get(pk=employee_id)
        salary, formset = create_or_update_salary(employee, month)

        if formset.is_valid():
            for form in formset:
                salary_item = form.cleaned_data['salary_item']
                value = form.cleaned_data['value']
                detail, created = SalaryDetail.objects.get_or_create(
                    salary=salary,
                    salary_item=salary_item
                )
                detail.value = value
                detail.save()
            return HttpResponseRedirect('success-url')
    else:
        employee_id = request.GET.get('employee', None)
        month = request.GET.get('month', None)
        if employee_id and month:
            employee = Employee.objects.get(pk=employee_id)
            _, formset = create_or_update_salary(employee, month)
        else:
            formset = None

    context = {
        'formset': formset,
        'employees': employees,
        'logged_data': getLoggedData(request)
    }
    return render(request, 'salary/salary_list.html', context)


@login_required
def save_salary_details(request):
    formset = SalaryDetailFormSet(request.POST)
    if formset.is_valid():
        formset.save()
    context = {'formset': formset, 'logged_data': getLoggedData(request)}
    return render(request, 'salary/salary_list.html', context)


@login_required
def get_filtered_employees(request):
    responsibility_level = request.GET.get('responsibility_level')
    employees = Employee.objects.filter(rank__value__lte=responsibility_level)
    return JsonResponse([{'id': employee.id, 'name': str(employee)} for employee in employees], safe=False)


@login_required
def create_task(request):
    if request.method == 'POST':
        form = TaskCreationForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.save()
    else:
        form = TaskCreationForm()

    context = {'form': form, 'logged_data': getLoggedData(request)}
    return render(request, 'tasks/task_create.html', context)


@login_required
def tasks_list(request):
    tasks = Task.objects.all()
    context = {'tasks': tasks, 'logged_data': getLoggedData(request)}
    return render(request, 'tasks/task_list.html', context)


@login_required
def create_schedule(request):
    schedule_items = []
    url = "/schedule/plan"
    if request.method == 'POST':
        schedule_date = request.POST.get('schedule_date')
        start_time = request.POST.get('start_time')
        end_time = request.POST.get('end_time')
        schedule_name = request.POST.get('schedule_name')

        tasks = json.loads(request.POST.get('tasks'))
        employees = json.loads(request.POST.get('employees'))
        scheduleItems = json.loads(request.POST.get('scheduleItems'))

        is_template = True if schedule_name else False

        if tasks and employees and scheduleItems:
            schedule = Schedule.objects.create(date=schedule_date, start_time=start_time, end_time=end_time,
                                               schedule_name=schedule_name, is_template=is_template)

            for task in tasks:
                total_time = timedelta(minutes=task['total_duration'])
                total_assigned_time = timedelta(minutes=task['total_assigned_time'])
                ScheduleTask.objects.create(schedule=schedule, task_id=task['task_id'], total_time=total_time,
                                            total_assigned_time=total_assigned_time)

            for employee in employees:
                working_hours = timedelta(minutes=employee['working_hours'])
                total_assigned_time = timedelta(minutes=employee['total_assigned_hours'])
                ScheduleEmployee.objects.create(schedule=schedule, employee_id=employee['employee_id'],
                                                working_hours=working_hours, total_assigned_time=total_assigned_time)

            for scheduleItem in scheduleItems:
                assigned_time = timedelta(minutes=scheduleItem['assigned_time'])
                employee = Employee.objects.get(id=scheduleItem['employee_id'])
                task = Task.objects.get(id=scheduleItem['task_id'])
                ScheduleItem.objects.create(
                    schedule=schedule,
                    employee=employee,
                    task=task,
                    assigned_time=assigned_time,
                    progression_rate=0
                )

            generate_schedule_items_for_stock_operations(schedule)

            if is_template:
                return JsonResponse({'success': True, 'url': url})
            else:
                schedule_service.update_all_schedule_statuses()
                return redirect('schedule_details')

    else:
        tasks_objects = Task.objects.exclude(task_type__in=[3, 4]).order_by('responsibility_level', 'priority')
        tasks = {}
        for task in tasks_objects:
            task_type = task.task_type
            tasks.setdefault(task_type, []).append(task)

        employees_objects = Employee.objects.all().order_by('rank')
        employees = {}
        for employee in employees_objects:
            employee_rank = employee.rank
            employees.setdefault(employee_rank, []).append(employee)

        teams = Team.objects.all()
        context = {'tasks': tasks,
                   'employees': employees,
                   'schedule_items': schedule_items,
                   'teams': teams,
                   'logged_data': getLoggedData(request)}
        return render(request, 'schedule/create_schedule.html', context)


@login_required
def scheduleItem_update(request, pk):
    schedule_service.update_all_schedule_statuses()
    referer = request.META.get('HTTP_REFERER')
    schedule_item = get_object_or_404(ScheduleItem, pk=pk)

    if request.method == 'POST':
        form = ScheduleItemForm(request.POST, instance=schedule_item)
        if form.is_valid() and referer:
            model_form = form.save(commit=False)

            new_item, assigned_delta = schedule_service.update_schedule_from_item(
                employee_id=model_form.employee.id,
                task_id=model_form.task.id,
                schedule_id=model_form.schedule.id,
                assigned_time=model_form.assigned_time,
                progression_rate=model_form.progression_rate,
                task_identifier=schedule_item.task_identifier if schedule_item.task_identifier else None,
                item_id=pk
            )
            schedule_service.update_employee_task_from_item(new_item, assigned_delta)

            return redirect(referer, schedule_id=schedule_item.schedule.id)
        else:
            form = ScheduleItemForm(instance=schedule_item)
            context = {'form': form, 'logged_data': getLoggedData(request)}
            return render(request, 'schedule/schedule_item_update.html', context)


@login_required
def schedule_items_for_schedule(request, schedule_id):
    schedule_service.update_all_schedule_statuses()
    schedule = get_object_or_404(Schedule, pk=schedule_id)
    schedule_tasks = ScheduleTask.objects.filter(schedule=schedule)
    schedule_employees = ScheduleEmployee.objects.filter(schedule=schedule)
    context = {'schedule': schedule,
               'schedule_tasks': schedule_tasks,
               'schedule_employees': schedule_employees,
               'logged_data': getLoggedData(request)}
    return render(request, 'schedule/schedule_items_for_schedule.html', context)


@login_required
def schedule_details2(request, schedule_id=None):
    schedule_service.update_all_schedule_statuses()
    selected_schedule = None
    employees = Employee.objects.all()
    tasks = Task.objects.all()
    form = ScheduleSelectionForm(request.POST or None)

    if schedule_id:
        selected_schedule = schedule_id
    elif form.is_valid():
        selected_schedule = form.cleaned_data['schedule']

    if selected_schedule:
        schedule_items = ScheduleItem.objects.filter(schedule=selected_schedule)
        schedule_employees = ScheduleEmployee.objects.filter(schedule=selected_schedule)
        schedule_tasks = ScheduleTask.objects.filter(schedule=selected_schedule)
        schedule_model = Schedule.objects.get(pk=selected_schedule)

        context = {
            'selected_schedule': selected_schedule,
            'schedule_details': schedule_items,
            'schedule_employees': schedule_employees,
            'schedule_tasks': schedule_tasks,
            'employees': employees,
            'tasks': tasks,
            'schedule_date': schedule_model.date,
            'start_time': schedule_model.start_time,
            'end_time': schedule_model.end_time,
            'logged_data': getLoggedData(request)
        }
        return render(request, 'schedule/schedule_details2.html', context)
    else:
        form = ScheduleSelectionForm()

    context = {'form': form,
               'employees': employees,
               'tasks': tasks,
               'logged_data': getLoggedData(request)}
    return render(request, 'schedule/schedule_details2.html', context)


@login_required
def add_or_edit_schedule_item(request, item_id=None):
    referer = request.META.get('HTTP_REFERER')
    employees = Employee.objects.all()
    tasks = Task.objects.all()

    if request.method == 'POST':
        schedule_id = request.POST.get('schedule')
        form = ScheduleItemAddEditForm(request.POST)
        if form.is_valid() and referer:
            schedule_item, assigned_delta = schedule_service.update_schedule_from_item(
                employee_id=form.cleaned_data['employee'].id,
                task_id=form.cleaned_data['task'].id,
                schedule_id=schedule_id,
                assigned_time=form.cleaned_data['assigned_time'],
                progression_rate=form.cleaned_data['progression_rate'] if form.cleaned_data[
                                                                              'progression_rate'] != '' else None
            )

            schedule_service.update_employee_task_from_item(schedule_item, assigned_delta)
            return redirect(referer, schedule_id=schedule_item.schedule.id)
        else:
            return redirect(referer, schedule_id=schedule_id)
    else:
        schedule_item = get_object_or_404(ScheduleItem, pk=item_id) if item_id else None
        context = {'employees': employees,
                   'tasks': tasks,
                   'schedule_item': schedule_item,
                   'logged_data': getLoggedData(request)}
        return render(request, 'schedule_details.html', context)


@login_required
def get_model_form(request):
    if request.method == 'POST':
        task_id = request.POST.get('task_id')
        employee_id = request.POST.get('employee_id')
        schedule_id = request.POST.get('selected_schedule')
        task = Task.objects.get(pk=task_id)

        try:
            model_name = task.progress_query.parameters['model_name']
            model = apps.get_model('ounissi_app', model_name)
            form_class_name = model.get_form()
            form_class = import_string(f'ounissi_app.forms.{form_class_name}')
            form = form_class()

            transfer_data = json.dumps({'task_id': task_id,
                                        'employee_id': employee_id,
                                        'schedule_id': schedule_id})

            context = {'form': form,
                       'form_title': task.task_name,
                       'form_class_name': form_class_name,
                       'transfer_data': transfer_data,
                       'logged_data': getLoggedData(request)}
            return render(request, 'tasks/model_form.html', context)

        except (Task.DoesNotExist, KeyError, LookupError, Exception) as ex:
            return JsonResponse({'success': False, 'message': f"Error: {str(ex)}"})


@login_required
def generic_form_submission_view(request, form_class_name):
    if request.method == 'POST':
        referer = request.META.get('HTTP_REFERER')
        form_class = import_string(f'ounissi_app.forms.{form_class_name}')
        form = form_class(request.POST)

        if form.is_valid():
            model_form = form.save(commit=False)
            model_form.created_by = request.user
            transfer_data = json.loads(request.POST.get('transfer_data'))
            task = Task.objects.get(pk=transfer_data['task_id'])

            schedule_item, assigned_delta = schedule_service.update_schedule_from_item(
                task_id=task.id,
                assigned_time=task.average_duration,
                schedule_id=transfer_data['schedule_id'],
                employee_id=transfer_data['employee_id'],
                task_identifier=form.cleaned_data['task_identifier'],
                progression_rate=100
            )

            schedule_service.generate_group_task(schedule_item, schedule_item.schedule)
            schedule_service.update_employee_task_from_item(schedule_item, assigned_delta)

            model_form.related_item = schedule_item
            model_form.save()
            return redirect(referer)
        else:
            messages.error(request, 'Please correct the errors below.')

    return JsonResponse({'success': False, 'message': 'Invalid request method.'})


def get_special_form(request):
    referer = request.META.get('HTTP_REFERER')
    if request.method == 'POST':
        item_id = request.POST.get('schedule_item')
        task_id = request.POST.get('task_id')

        task = Task.objects.get(pk=task_id)
        schedule_item = ScheduleItem.objects.get(pk=item_id)
        try:
            model_name = task.progress_query.parameters['model_name']
            model = apps.get_model('ounissi_app', model_name)
            form_class_name = model.get_form()
            employees = ScheduleEmployee.objects.filter(schedule=schedule_item.schedule,
                                                        employee__rank__value__lte=task.responsibility_level.value)

            form_template = f'special_forms/{form_class_name}.html'
            original_item = schedule_service.get_original_item(schedule_item)
            original_model = apps.get_model('ounissi_app', original_item.task.progress_query.parameters['model_name'])
            original_task = schedule_service.get_related_item_details(original_item, original_model)[0]
            items_list = []
            invoice = None

            if form_class_name in ['ReceptionVignetteForm', 'ReceptionProduitForm', 'ReceptionPlacementForm']:
                query = Query.objects.get(name='InvoiceHelper')
                parameters = query.parameters.copy()
                parameters['ref_tiers'] = original_task.ref_tiers
                parameters['supplier'] = original_task.supplier

                invoice = get_query_results(query, parameters)
                for item in invoice['QUANTITE']:
                    items_list.append(int(item) * int(original_item.task.average_duration.total_seconds()))
            else:
                try:
                    for i in range(original_task.number_of_lines):
                        items_list.append(int(original_item.task.average_duration.total_seconds()))
                except:
                    items_list.append(int(original_item.task.average_duration.total_seconds()))

            context = {
                'model_schedule_item': schedule_item,
                'model_employees': employees,
                'original_task': original_task,
                'items_list': items_list,
                'invoice': invoice,
            }
            return render(request, form_template, context)

        except (Task.DoesNotExist, KeyError, LookupError, Exception) as ex:
            return JsonResponse({'success': False, 'message': f"Error: {str(ex)}"})

    return redirect(referer)


def special_form_saisie(request):
    referer = request.META.get('HTTP_REFERER')
    if request.method == 'POST':
        form = SaisieForm(request.POST)
        if form.is_valid():
            model_form = form.save(commit=False)
            task_id = model_form.employee1_schedule_item.task.id
            task_identifier = model_form.employee1_schedule_item.task_identifier
            schedule_id = model_form.employee1_schedule_item.schedule.id
            average_duration = model_form.employee1_schedule_item.task.average_duration

            model_form.employee1_schedule_item.employee = model_form.employee1
            assigned_time_1 = average_duration * (1 + model_form.employee1_range_end - model_form.employee1_range_start)
            task_identifier1 = f"{task_identifier}Lines:{model_form.employee1_range_start}<>{model_form.employee1_range_end}"

            schedule_item, assigned_delta = schedule_service.update_schedule_from_item(
                task_id=task_id,
                assigned_time=assigned_time_1,
                schedule_id=schedule_id,
                employee_id=model_form.employee1.id,
                task_identifier=task_identifier1,
                item_id=model_form.employee1_schedule_item.id
            )

            schedule_service.generate_group_task(schedule_item, schedule_item.schedule)
            schedule_service.update_employee_task_from_item(schedule_item, assigned_delta)

            if model_form.employee2 and model_form.employee2_range_start and model_form.employee2_range_end:
                assigned_time_2 = average_duration * (
                            1 + model_form.employee2_range_end - model_form.employee2_range_start)
                task_identifier2 = f"{task_identifier}Lines:{model_form.employee2_range_start}<>{model_form.employee2_range_end}"

                model_form.employee2_schedule_item, assigned_delta = schedule_service.update_schedule_from_item(
                    task_id=task_id,
                    assigned_time=assigned_time_2,
                    schedule_id=schedule_id,
                    employee_id=model_form.employee2.id,
                    task_identifier=task_identifier2
                )
                schedule_service.update_employee_task_from_item(model_form.employee2_schedule_item, assigned_delta)

                if model_form.employee3 and model_form.employee3_range_start and model_form.employee3_range_end:
                    assigned_time_3 = average_duration * (
                                1 + model_form.employee3_range_end - model_form.employee3_range_start)
                    task_identifier3 = f"{task_identifier}Lines:{model_form.employee3_range_start}<>{model_form.employee3_range_end}"

                    model_form.employee3_schedule_item, assigned_delta = schedule_service.update_schedule_from_item(
                        task_id=task_id,
                        assigned_time=assigned_time_3,
                        schedule_id=schedule_id,
                        employee_id=model_form.employee3.id,
                        task_identifier=task_identifier3
                    )
                    schedule_service.update_employee_task_from_item(model_form.employee3_schedule_item, assigned_delta)
            form.save()
        return redirect(referer)


def special_form_produit(request):
    referer = request.META.get('HTTP_REFERER')
    if request.method == 'POST':
        form = ReceptionProduitForm(request.POST)
        if form.is_valid():
            model_form = form.save(commit=False)
            task_id = model_form.employee1_schedule_item.task.id
            task_identifier = model_form.employee1_schedule_item.task_identifier
            schedule_id = model_form.employee1_schedule_item.schedule.id
            average_duration = model_form.employee1_schedule_item.task.average_duration

            assigned_time_1 = average_duration * (1 + model_form.employee1_range_end - model_form.employee1_range_start)
            task_identifier1 = f"{task_identifier}Lines:{model_form.employee1_range_start}<>{model_form.employee1_range_end}"

            schedule_item, assigned_delta = schedule_service.update_schedule_from_item(
                task_id=task_id,
                assigned_time=assigned_time_1,
                schedule_id=schedule_id,
                employee_id=model_form.employee1.id,
                task_identifier=task_identifier1,
                item_id=model_form.employee1_schedule_item.id
            )

            schedule_service.generate_group_task(schedule_item, schedule_item.schedule)
            schedule_service.update_employee_task_from_item(schedule_item, assigned_delta)

            if model_form.employee2 and model_form.employee2_range_start and model_form.employee2_range_end:
                assigned_time_2 = average_duration * (
                            1 + model_form.employee2_range_end - model_form.employee2_range_start)
                task_identifier2 = f"{task_identifier}Lines:{model_form.employee2_range_start}<>{model_form.employee2_range_end}"

                model_form.employee2_schedule_item, assigned_delta = schedule_service.update_schedule_from_item(
                    task_id=task_id,
                    assigned_time=assigned_time_2,
                    schedule_id=schedule_id,
                    employee_id=model_form.employee2.id,
                    task_identifier=task_identifier2
                )
                schedule_service.update_employee_task_from_item(model_form.employee2_schedule_item, assigned_delta)

                if model_form.employee3 and model_form.employee3_range_start and model_form.employee3_range_end:
                    assigned_time_3 = average_duration * (
                                1 + model_form.employee3_range_end - model_form.employee3_range_start)
                    task_identifier3 = f"{task_identifier}Lines:{model_form.employee3_range_start}<>{model_form.employee3_range_end}"

                    model_form.employee3_schedule_item, assigned_delta = schedule_service.update_schedule_from_item(
                        task_id=task_id,
                        assigned_time=assigned_time_3,
                        schedule_id=schedule_id,
                        employee_id=model_form.employee3.id,
                        task_identifier=task_identifier3
                    )
                    schedule_service.update_employee_task_from_item(model_form.employee3_schedule_item, assigned_delta)
            form.save()
        return redirect(referer)


def special_form_vignette(request):
    referer = request.META.get('HTTP_REFERER')
    if request.method == 'POST':
        form = ReceptionVignetteForm(request.POST)
        if form.is_valid():
            model_form = form.save(commit=False)
            task_id = model_form.employee1_schedule_item.task.id
            task_identifier = model_form.employee1_schedule_item.task_identifier
            schedule_id = model_form.employee1_schedule_item.schedule.id
            average_duration = model_form.employee1_schedule_item.task.average_duration

            assigned_time_1 = average_duration * (1 + model_form.employee1_range_end - model_form.employee1_range_start)
            task_identifier1 = f"{task_identifier}Lines:{model_form.employee1_range_start}<>{model_form.employee1_range_end}"

            schedule_item, assigned_delta = schedule_service.update_schedule_from_item(
                task_id=task_id,
                assigned_time=assigned_time_1,
                schedule_id=schedule_id,
                employee_id=model_form.employee1.id,
                task_identifier=task_identifier1,
                item_id=model_form.employee1_schedule_item.id
            )

            schedule_service.generate_group_task(schedule_item, schedule_item.schedule)
            schedule_service.update_employee_task_from_item(schedule_item, assigned_delta)

            if model_form.employee2 and model_form.employee2_range_start and model_form.employee2_range_end:
                assigned_time_2 = average_duration * (
                            1 + model_form.employee2_range_end - model_form.employee2_range_start)
                task_identifier2 = f"{task_identifier}Lines:{model_form.employee2_range_start}<>{model_form.employee2_range_end}"

                model_form.employee2_schedule_item, assigned_delta = schedule_service.update_schedule_from_item(
                    task_id=task_id,
                    assigned_time=assigned_time_2,
                    schedule_id=schedule_id,
                    employee_id=model_form.employee2.id,
                    task_identifier=task_identifier2
                )
                schedule_service.update_employee_task_from_item(model_form.employee2_schedule_item, assigned_delta)

                if model_form.employee3 and model_form.employee3_range_start and model_form.employee3_range_end:
                    assigned_time_3 = average_duration * (
                                1 + model_form.employee3_range_end - model_form.employee3_range_start)
                    task_identifier3 = f"{task_identifier}Lines:{model_form.employee3_range_start}<>{model_form.employee3_range_end}"

                    model_form.employee3_schedule_item, assigned_delta = schedule_service.update_schedule_from_item(
                        task_id=task_id,
                        assigned_time=assigned_time_3,
                        schedule_id=schedule_id,
                        employee_id=model_form.employee3.id,
                        task_identifier=task_identifier3
                    )
                    schedule_service.update_employee_task_from_item(model_form.employee3_schedule_item, assigned_delta)
            form.save()
        return redirect(referer)


def special_form_placement(request):
    referer = request.META.get('HTTP_REFERER')
    if request.method == 'POST':
        form = ReceptionPlacementForm(request.POST)
        if form.is_valid():
            model_form = form.save(commit=False)
            task_id = model_form.employee1_schedule_item.task.id
            task_identifier = model_form.employee1_schedule_item.task_identifier
            schedule_id = model_form.employee1_schedule_item.schedule.id
            average_duration = model_form.employee1_schedule_item.task.average_duration

            assigned_time_1 = average_duration * (1 + model_form.employee1_range_end - model_form.employee1_range_start)
            task_identifier1 = f"{task_identifier}Lines:{model_form.employee1_range_start}<>{model_form.employee1_range_end}"

            schedule_item, assigned_delta = schedule_service.update_schedule_from_item(
                task_id=task_id,
                assigned_time=assigned_time_1,
                schedule_id=schedule_id,
                employee_id=model_form.employee1.id,
                task_identifier=task_identifier1,
                item_id=model_form.employee1_schedule_item.id
            )

            schedule_service.generate_group_task(schedule_item, schedule_item.schedule)
            schedule_service.update_employee_task_from_item(schedule_item, assigned_delta)

            if model_form.employee2 and model_form.employee2_range_start and model_form.employee2_range_end:
                assigned_time_2 = average_duration * (
                            1 + model_form.employee2_range_end - model_form.employee2_range_start)
                task_identifier2 = f"{task_identifier}Lines:{model_form.employee2_range_start}<>{model_form.employee2_range_end}"

                model_form.employee2_schedule_item, assigned_delta = schedule_service.update_schedule_from_item(
                    task_id=task_id,
                    assigned_time=assigned_time_2,
                    schedule_id=schedule_id,
                    employee_id=model_form.employee2.id,
                    task_identifier=task_identifier2
                )
                schedule_service.update_employee_task_from_item(model_form.employee2_schedule_item, assigned_delta)

                if model_form.employee3 and model_form.employee3_range_start and model_form.employee3_range_end:
                    assigned_time_3 = average_duration * (
                                1 + model_form.employee3_range_end - model_form.employee3_range_start)
                    task_identifier3 = f"{task_identifier}Lines:{model_form.employee3_range_start}<>{model_form.employee3_range_end}"

                    model_form.employee3_schedule_item, assigned_delta = schedule_service.update_schedule_from_item(
                        task_id=task_id,
                        assigned_time=assigned_time_3,
                        schedule_id=schedule_id,
                        employee_id=model_form.employee3.id,
                        task_identifier=task_identifier3
                    )
                    schedule_service.update_employee_task_from_item(model_form.employee3_schedule_item, assigned_delta)
            form.save()
        return redirect(referer)


def get_query_results(query, parameters):
    schedule_service.update_all_schedule_statuses()
    try:
        if query.type == 0:
            with connection.cursor() as cursor:
                cursor.execute(query.query, parameters)
                results = cursor.fetchall()

                columns = [col[0] for col in cursor.description]
                data_rows = []
                op_user_index = columns.index('OP_USER') if 'OP_USER' in columns else -1

                for row in results:
                    row_list = list(row)
                    if op_user_index != -1:
                        try:
                            user_id = row_list[op_user_index]
                            xp_id = User.objects.get(pk=user_id).employee.xp_id
                            row_list[op_user_index] = xp_id
                        except Exception:
                            pass
                    data_rows.append(tuple(row_list))

            return {'columns': columns, 'data_rows': data_rows}
        else:
            conn = XpertConnect()
            conn.open_session()
            query_results = conn.run_query(query.query, parameters)
            conn.close_session()
            return query_results
    except Exception as ex:
        return {'error': str(ex)}


def update_schedule_now(request, schedule_id=None):
    referer = request.META.get('HTTP_REFERER')
    try:
        schedule = Schedule.objects.get(pk=schedule_id)
        if schedule:
            schedule_service.update_schedule_progress(schedule)
    except Exception:
        pass
    return redirect(referer)


def finalize_schedule(request, schedule_id):
    referer = request.META.get('HTTP_REFERER')
    unfinished_tasks = {}
    schedule = get_object_or_404(Schedule, id=schedule_id)
    unfinished_items = ScheduleItem.objects.filter(schedule=schedule, progression_rate__lt=100, task__transfer=True)

    if unfinished_items.exists():
        for item in unfinished_items:
            remaining_time = item.assigned_time - (item.progress_lines * item.task.average_duration)

            if item.task_identifier:
                task_key = f"{item.task.id}_{item.task_identifier.split('Lines')[0]}"
            else:
                task_key = f"{item.task.id}"

            if task_key in unfinished_tasks:
                unfinished_tasks[task_key]['remaining_time'] += remaining_time.total_seconds()
            else:
                unfinished_tasks[task_key] = {
                    'task': item.task.id,
                    'remaining_time': remaining_time.total_seconds(),
                }
                if item.task_identifier:
                    unfinished_tasks[task_key]['task_identifier'] = item.task_identifier.split('Lines')[0]

        request.session['unfinished_tasks'] = unfinished_tasks
        return redirect('unfinished_tasks', schedule_id=schedule_id)

    schedule.schedule_status = 3  # 'Clôturé'
    schedule.save()
    return redirect(referer)


def handle_unfinished_tasks(request, schedule_id):
    schedule = get_object_or_404(Schedule, id=schedule_id)
    unfinished_tasks = request.session.get('unfinished_tasks', {})

    task_details = []
    for task_info in unfinished_tasks.values():
        task = Task.objects.get(id=task_info['task'])
        remaining_time = timedelta(seconds=task_info['remaining_time'])
        task_identifier = task_info.get('task_identifier', '')

        task_details.append({
            'task': task,
            'remaining_time': remaining_time,
            'task_identifier': task_identifier,
        })

    if request.method == 'POST':
        if 'finish_all' in request.POST:
            overdue_tasks = ScheduleTask.objects.filter(schedule=schedule, status__in=[0, 1])
            overdue_tasks.update(status=3)
        else:
            transfer_tasks = request.POST.getlist('transfer_tasks')

            transfer_schedule, created = Schedule.objects.get_or_create(
                schedule_name='Transfer_Schedule',
                defaults={'schedule_status': 0, 'is_template': True,
                          'start_time': datetime.min.time(), 'end_time': datetime.max.time()}
            )

            overdue_tasks = []
            for task_detail in task_details:
                schedule_tasks = ScheduleTask.objects.filter(schedule=schedule,
                                                             task_id=task_detail['task'].id,
                                                             completion__gt=0)

                if str(task_detail['task'].id) in transfer_tasks:
                    schedule_tasks.update(status=4)
                    existing_item = ScheduleItem.objects.filter(
                        schedule=transfer_schedule,
                        task_id=task_detail['task'].id,
                        task_identifier=task_detail['task_identifier']
                    ).first()

                    if existing_item:
                        existing_item.assigned_time += task_detail['remaining_time']
                        existing_item.save()
                    else:
                        ScheduleItem.objects.create(
                            schedule=transfer_schedule,
                            task_id=task_detail['task'].id,
                            assigned_time=task_detail['remaining_time'],
                            task_identifier=task_detail['task_identifier'],
                        )
                else:
                    overdue_tasks.append(task_detail['task'].id)

            if overdue_tasks:
                ScheduleTask.objects.filter(schedule=schedule, task_id__in=overdue_tasks).update(status=3)

        schedule.schedule_status = 3
        schedule.save()
        messages.success(request, "Schedule finalized and closed.")
        return redirect('schedule_details')

    else:
        return render(request, 'schedule/schedule_close.html', {
            'schedule': schedule,
            'unfinished_tasks': task_details,
            'logged_data': getLoggedData(request),
        })


def import_tasks(request):
    referer = request.META.get('HTTP_REFERER')
    if request.method == 'POST':
        actual_schedule_id = request.POST.get('actual_schedule')
        actual_schedule = Schedule.objects.get(pk=actual_schedule_id)
        selected_items = request.POST.getlist('transfer_items')

        for item_id in selected_items:
            item = ScheduleItem.objects.get(id=item_id)
            employee_id = request.POST.get(f'employee_{item_id}')

            if item.task_identifier:
                ScheduleItem.objects.create(
                    task=item.task,
                    schedule=actual_schedule,
                    task_identifier=item.task_identifier
                )
                item.delete()
            else:
                assigned_time_str = request.POST.get(f'assigned_time_{item_id}')
                assigned_time = datetime.strptime(assigned_time_str, '%H:%M:%S')
                assigned_seconds = assigned_time.hour * 3600 + assigned_time.minute * 60 + assigned_time.second

                ScheduleItem.objects.create(
                    task=item.task,
                    schedule=actual_schedule,
                    assigned_time=timedelta(seconds=assigned_seconds),
                    employee_id=employee_id,
                    task_identifier=item.task_identifier
                )

                if timedelta(seconds=assigned_seconds) >= item.assigned_time:
                    item.delete()
                else:
                    item.assigned_time -= timedelta(seconds=assigned_seconds)
                    item.save()

        return redirect(referer)


######### STOCK PART #################
def get_emplacements(request):
    query = get_object_or_404(Query, name='STOCK EMPLACEMENTS')
    emplacements = get_query_results(query, query.parameters)
    context = {
        'logged_data': getLoggedData(request),
        'emplacements': emplacements
    }
    return render(request, 'stock/emplacements.html', context)


def get_stock(request):
    query = get_object_or_404(Query, name='TEST STOCK')
    stock = get_query_results(query, query.parameters)
    context = {
        'logged_data': getLoggedData(request),
        'stock': stock
    }
    return render(request, 'stock/stocks.html', context)


def assign_stock(request):
    get_active_assignments()

    employees = Employee.objects.all()
    operations = StockOperation.objects.all()

    group_size = request.GET.get('group_by', 3)
    grouped_emplacements = get_emplacemnt_groupped(int(group_size))

    today = date.today()
    assigned_emplacements = AssignationEmplacement.objects.filter(
        date_debut__lte=today, date_fin__gte=today
    )

    assigned_emplacements_dict = {}
    for assignment in assigned_emplacements:
        key = assignment.emplacement
        if key not in assigned_emplacements_dict:
            assigned_emplacements_dict[key] = []
        assigned_emplacements_dict[key].append(assignment)

    if request.method == 'GET':
        group_size = request.GET.get('group_by')
        if group_size:
            grouped_emplacements = get_emplacemnt_groupped(int(group_size))

        context = {
            'logged_data': getLoggedData(request),
            'grouped_emplacements': grouped_emplacements,
            'employees': employees,
            'operations': operations,
            'assigned_emplacements_dict': assigned_emplacements_dict
        }
        return render(request, 'stock/assign_stock.html', context)

    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            response_data = []
            for item in data:
                emplacement = item.get('emplacement')
                employee_id = item.get('employee')
                date_debut = item.get('date_debut')
                date_fin = item.get('date_fin')
                operations = item.get('operations', [])
                if emplacement and employee_id and date_debut and date_fin and operations:
                    employee = Employee.objects.filter(pk=employee_id).first()
                    for operation in operations:
                        operation = StockOperation.objects.filter(designation=operation).first()
                        if not operation:
                            continue

                        assignation_instance = AssignationEmplacement.objects.filter(
                            emplacement=emplacement,
                            operation=operation
                        ).first()

                        if assignation_instance:
                            assignation_instance.employee = employee
                            assignation_instance.date_debut = date_debut
                            assignation_instance.date_fin = date_fin
                        else:
                            assignation_instance = AssignationEmplacement(
                                emplacement=emplacement,
                                employee=employee,
                                operation=operation,
                                date_debut=date_debut,
                                date_fin=date_fin,
                            )
                        assignation_instance.clean()
                        assignation_instance.save()
                else:
                    return JsonResponse({'Erreur dans': str(emplacement)}, status=500)

            return JsonResponse({'message': 'Details!', 'data': response_data}, status=200)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


def delete_assignment(request, assignment_id):
    if request.method == 'DELETE':
        try:
            assignment = AssignationEmplacement.objects.get(pk=assignment_id)
            assignment.delete()
            return JsonResponse({'success': True, 'message': 'Assignment deleted successfully.'}, status=200)
        except AssignationEmplacement.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Assignment not found.'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    return JsonResponse({'success': False, 'error': 'Invalid request method.'}, status=400)


def get_emplacemnt_groupped(x=3):
    query = get_object_or_404(Query, name='LISTE EMPLACEMENT')
    emplacements = get_query_results(query, query.parameters)
    grouped_emplacements = {}
    for emplacement in emplacements['data_rows']:
        prefix = emplacement[0][:x]  # Assuming DESIGNATION is the first item
        if prefix not in grouped_emplacements:
            grouped_emplacements[prefix] = []
        grouped_emplacements[prefix].append(emplacement[0])
    return grouped_emplacements


def get_active_assignments():
    today = date.today()
    return AssignationEmplacement.objects.filter(date_debut__lte=today, date_fin__gte=today)


def get_emplacement_item_count(emplacement, type_count='Prd'):
    query = Query.objects.get(name="STOCK EMPLACEMENTS")
    parameters = {"emp": emplacement}
    results = get_query_results(query, parameters)
    count = 0
    try:
        # Recreating the logic without pandas:
        # Count unique items based on column index
        if type_count == 'Bte':
            qte_index = results['columns'].index('QUANTITE')
            count = sum(row[qte_index] for row in results['data_rows'])
        elif type_count == 'Prd':
            des_index = results['columns'].index('DESIGNATION')
            count = len(set(row[des_index] for row in results['data_rows']))
        elif type_count == 'Lot':
            lot_index = results['columns'].index('CODE_BARRE_LOT')
            count = len(set(row[lot_index] for row in results['data_rows']))
        elif type_count == 'Emp':
            emp_index = results['columns'].index('EMPLACEMENT')
            count = len(set(row[emp_index] for row in results['data_rows']))
    except Exception:
        count = 0
    return count


def generate_schedule_items_for_stock_operations(schedule):
    active_assignments = AssignationEmplacement.objects.filter(
        date_debut__lte=date.today(),
        date_fin__gte=date.today()
    )

    for assignment in active_assignments:
        employee = assignment.employee
        stock_operation = assignment.operation
        emplacement = assignment.emplacement

        task = stock_operation.task
        if not task:
            continue

        item_count = get_emplacement_item_count(emplacement)
        if item_count == 0:
            continue

        assigned_time = stock_operation.duration * item_count

        if not schedule:
            continue

        schedule_task, created_task = ScheduleTask.objects.get_or_create(
            schedule=schedule,
            task=task,
            defaults={
                'total_time': assigned_time,
                'total_assigned_time': assigned_time,
                'status': 0,
                'completion': 0,
            }
        )
        if not created_task:
            schedule_task.total_assigned_time += assigned_time
            schedule_task.save()

        schedule_employee, created_employee = ScheduleEmployee.objects.get_or_create(
            schedule=schedule,
            employee=employee,
            defaults={
                'total_assigned_time': assigned_time,
                'score': 0,
            }
        )
        if not created_employee:
            schedule_employee.total_assigned_time += assigned_time
            schedule_employee.save()

        schedule_item, created_item = ScheduleItem.objects.get_or_create(
            schedule=schedule,
            task=task,
            employee=employee,
            defaults={
                'assigned_time': assigned_time,
                'progression_rate': 0,
                'task_identifier': f": {emplacement}"
            }
        )
        if not created_item:
            schedule_item.assigned_time += assigned_time
            schedule_item.save()


@login_required
def actual_schedule_details(request, schedule_id=None):
    schedule_service.update_all_schedule_statuses()

    if schedule_id:
        schedule = get_object_or_404(Schedule, pk=schedule_id)
        actual = False
    else:
        schedule = schedule_service.get_current_active_schedule()
        actual = schedule is not None

    sched_data = schedule_service.get_schedule_context_data(schedule)

    context = {
        'actual': actual,
        'selected_schedule': schedule,
        'employees': Employee.objects.all(),
        'tasks': Task.objects.all(),
        'transfer_items': ScheduleItem.objects.filter(schedule__schedule_name='Transfer_Schedule'),
        'logged_data': getLoggedData(request)
    }

    if sched_data:
        context.update(sched_data)

    return render(request, 'schedule/actual_schedule_details.html', context)


@login_required
def schedule_details(request, schedule_id=None):
    schedule_service.update_all_schedule_statuses()
    schedules = Schedule.objects.filter(is_template=False).exclude(schedule_status=1)

    schedule_filter_form = ScheduleFilterForm(request.GET)
    schedule_instance = None

    if schedule_filter_form.is_valid():
        schedule_filter = schedule_filter_form.cleaned_data.get('schedule')
        if schedule_filter:
            schedule_instance = schedules.filter(id=schedule_filter.id).first()

    schedule = get_object_or_404(Schedule, pk=schedule_id) if schedule_id else schedule_instance

    sched_data = schedule_service.get_schedule_context_data(schedule)

    context = {
        'actual': False,
        'schedules': schedules,
        'selected_schedule': schedule,
        'schedule_filter_form': schedule_filter_form,
        'logged_data': getLoggedData(request)
    }

    if sched_data:
        context.update(sched_data)

    return render(request, 'schedule/schedule_details.html', context)


@login_required
def schedule_current(request, schedule_id=None):
    logged_data = getLoggedData(request)
    employee = logged_data.get('employee')

    schedule = get_object_or_404(Schedule,
                                 pk=schedule_id) if schedule_id else schedule_service.get_current_active_schedule()
    current_schedule = schedule is not None

    sched_data = schedule_service.get_schedule_context_data(schedule, employee=employee)

    tasks_demande = []
    tasks_saisie = []

    if employee:
        tasks_demande = Task.objects.filter(task_type__name='DEMANDE',
                                            responsibility_level__gte=employee.rank).order_by('priority')
        tasks_saisie = Task.objects.filter(task_type__name='APRES SAISIE',
                                           responsibility_level__gte=employee.rank).order_by('priority')

    context = {
        'current_schedule': current_schedule,
        'selected_schedule': schedule,
        'tasks_demande': tasks_demande,
        'tasks_saisie': tasks_saisie,
        'logged_data': logged_data
    }

    if sched_data:
        context.update(sched_data)

    return render(request, 'portal/user_schedule.html', context)


@login_required
def user_schedules_history(request, schedule_id=None):
    schedule_service.update_all_schedule_statuses()
    logged_data = getLoggedData(request)
    employee = logged_data.get('employee')

    schedule_ids = ScheduleEmployee.objects.filter(employee=employee).values_list('schedule_id',
                                                                                  flat=True) if employee else []
    schedules = Schedule.objects.filter(id__in=schedule_ids, is_template=False).exclude(schedule_status=1)

    schedule_filter_form = ScheduleFilterForm(request.GET)
    schedule_instance = None
    if schedule_filter_form.is_valid():
        schedule_filter = schedule_filter_form.cleaned_data.get('schedule')
        if schedule_filter:
            schedule_instance = schedules.filter(id=schedule_filter.id).last()

    schedule = get_object_or_404(Schedule, pk=schedule_id) if schedule_id else schedule_instance

    sched_data = schedule_service.get_schedule_context_data(schedule, employee=employee)

    context = {
        'schedules': schedules,
        'selected_schedule': schedule,
        'schedule_filter_form': schedule_filter_form,
        'logged_data': logged_data
    }

    if sched_data:
        context.update(sched_data)

    return render(request, 'portal/user_schedule_history.html', context)


@login_required
def my_timesheet(request):
    employee = getattr(request.user, 'employee', None)
    if not employee:
        # Assuming you have an error or landing page for users without profiles
        return render(request, 'error.html', {'message': "Profil employé non trouvé."})

    # 1. Get Month/Year from GET params or default to 'now'
    today = timezone.localtime().date()
    try:
        selected_month = int(request.GET.get('month', today.month))
        selected_year = int(request.GET.get('year', today.year))
    except (ValueError, TypeError):
        selected_month, selected_year = today.month, today.year

    # 2. Filter Timesheets for the local database
    timesheets = Timesheet.objects.filter(
        employee=employee,
        date__year=selected_year,
        date__month=selected_month
    ).order_by('-date')

    # 3. Generate lists for the dropdown menus
    # Months 1-12 (French names if you prefer)
    months = [
        (1, 'Janvier'), (2, 'Février'), (3, 'Mars'), (4, 'Avril'),
        (5, 'Mai'), (6, 'Juin'), (7, 'Juillet'), (8, 'Août'),
        (9, 'Septembre'), (10, 'Octobre'), (11, 'Novembre'), (12, 'Décembre')
    ]
    # Last 3 years
    years = range(today.year, today.year - 2, -1)

    # 4. Quota check for today (remains current date specific)
    sync_record, _ = UserSyncLog.objects.get_or_create(user=request.user, date=today)
    remaining_syncs = max(0, 3 - sync_record.count)

    context = {
        'timesheets': timesheets,
        'selected_month': selected_month,
        'selected_year': selected_year,
        'months': months,
        'years': years,
        'remaining_syncs': remaining_syncs,
        'logged_data': getLoggedData(request) # Using your existing helper
    }

    return render(request, 'portal/my_timesheet.html', context)
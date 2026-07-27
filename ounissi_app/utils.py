from dateutil.relativedelta import relativedelta
from decimal import Decimal
from django.db.models import Sum
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


# method calculating start date default value for a salary
def calculate_start_date(month):
    return month - relativedelta(months=1)


# method calculating total salary from dependent salary detail records
def calculate_total_salary(salary, details):
    # Sum all SalaryDetail values related to this salary
    total = details.objects.filter(salary=salary).aggregate(total=Sum('amount'))['total']
    return total if total is not None else Decimal('0.0')


def get_actual_timesheet(employee):

    today_date = timezone.localtime().date()

    try:
        # Import here to avoid circular imports if utils is loaded early
        from .models import Timesheet

        timesheet = Timesheet.objects.filter(employee=employee, date=today_date).first()

        if timesheet and timesheet.start_time:
            return timesheet.start_time.strftime('%H:%M')

    except Exception as e:
        logger.error(f"Error fetching timesheet for {employee}: {e}")

    return None


def getLoggedData(request):

    loggedData = {
        'user': 'Not Connected',
        'group': None,
        'employee': None,
        'team': None,
        'leader': False,
        'team_members': [],
        'entrance': None,
    }

    if request.user.is_authenticated:
        loggedData['user'] = request.user

        # 1. Get Group (Safely)
        loggedData['group'] = request.user.groups.first()

        try:
            # 2. Get Employee and Team efficiently (using select_related)
            # This fetches the user's Employee profile and their Team in ONE database query
            employee = request.user.employee
            loggedData['employee'] = employee

            # 3. Get Entrance Time
            loggedData['entrance'] = get_actual_timesheet(employee)

            # 4. Handle Team & Leadership
            if hasattr(employee, 'team'):
                team = employee.team
                loggedData['team'] = team

                # Check if this user is the leader of their team
                if team.leader_id == employee.id:
                    loggedData['leader'] = True
                    # If they are the leader, fetch their team members
                    loggedData['team_members'] = list(team.employees.all())

        except Exception as e:
            # If the user has no employee profile, or something else fails
            logger.warning(f"Failed to fetch complete employee data for {request.user}: {e}")

    return loggedData


# exports.py
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from django.http import HttpResponse


def generate_timesheet_excel(timesheets_with_hours, start_date, end_date):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Pointages"
    ws.views.sheetView[0].showGridLines = True

    # Style configuration
    title_font = Font(name='Calibri', size=14, bold=True, color='1F4E78')
    header_font = Font(name='Calibri', size=11, bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='203764', end_color='203764', fill_type='solid')
    subheader_fill = PatternFill(start_color='305496', end_color='305496', fill_type='solid')

    border_thin = Side(border_style="thin", color="D9D9D9")
    cell_border = Border(left=border_thin, right=border_thin, top=border_thin, bottom=border_thin)

    # Title details block
    ws.append([])
    ws.cell(row=2, column=1, value="Contrôle des Présences / Pointages").font = title_font
    ws.cell(row=3, column=1, value=f"Période : {start_date.strftime('%d/%m/%Y')} au {end_date.strftime('%d/%m/%Y')}")
    ws.append([])
    ws.append([])

    # Table structure headers
    start_row = 6
    headers_r1 = [
        "Employé", "Date",
        "Session 1", "",
        "Session 2", "",
        "Session 3", "",
        "Bio Total",
        "Audit Xpert", "",
        "Alerte"
    ]
    headers_r2 = [
        "", "",
        "Début", "Fin",
        "Début", "Fin",
        "Début", "Fin",
        "",
        "Trace", "Total",
        ""
    ]

    ws.append(headers_r1)
    ws.append(headers_r2)

    # Merging layout cells
    ws.merge_cells(start_row=start_row, start_column=1, end_row=start_row + 1, end_column=1)  # Employee
    ws.merge_cells(start_row=start_row, start_column=2, end_row=start_row + 1, end_column=2)  # Date
    ws.merge_cells(start_row=start_row, start_column=3, end_row=start_row, end_column=4)  # Session 1
    ws.merge_cells(start_row=start_row, start_column=5, end_row=start_row, end_column=6)  # Session 2
    ws.merge_cells(start_row=start_row, start_column=7, end_row=start_row, end_column=8)  # Session 3
    ws.merge_cells(start_row=start_row, start_column=9, end_row=start_row + 1, end_column=9)  # Bio Total
    ws.merge_cells(start_row=start_row, start_column=10, end_row=start_row, end_column=11)  # Audit Xpert
    ws.merge_cells(start_row=start_row, start_column=12, end_row=start_row + 1, end_column=12)  # Warning

    # Styling cells
    for r in range(start_row, start_row + 2):
        for c in range(1, 13):
            cell = ws.cell(row=r, column=c)
            cell.font = header_font
            cell.fill = header_fill if r == start_row else subheader_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = cell_border

    # Fills for rows
    warning_fill = PatternFill(start_color='FFC7CE', end_color='FFC7CE', fill_type='solid')  # Soft Red
    confirmed_fill = PatternFill(start_color='C6EFCE', end_color='C6EFCE', fill_type='solid')  # Soft Green

    # Adding records
    for item in timesheets_with_hours:
        ts = item['obj']
        bio_seconds = item['hours'].total_seconds()
        bh, brem = divmod(int(bio_seconds), 3600)
        bm, _ = divmod(brem, 60)
        bio_hours_str = f"{bh:02d}:{bm:02d}" if bio_seconds > 0 else "00:00"

        row_data = [
            str(ts.employee),
            ts.date.strftime('%d/%m/%Y') if ts.date else "",
            ts.start_time.strftime('%H:%M') if ts.start_time else "",
            ts.end_time.strftime('%H:%M') if ts.end_time else "",
            ts.start_time_2.strftime('%H:%M') if ts.start_time_2 else "",
            ts.end_time_2.strftime('%H:%M') if ts.end_time_2 else "",
            ts.start_time_3.strftime('%H:%M') if ts.start_time_3 else "",
            ts.end_time_3.strftime('%H:%M') if ts.end_time_3 else "",
            bio_hours_str,
            f"{item['xp_first']} → {item['xp_last']}" if item['xp_first'] != '--' else "--",
            item['xp_total'],
            "Oui" if item['warning'] else "Non"
        ]
        ws.append(row_data)

        # Applying specific row color themes
        curr_row = ws.max_row
        row_fill = None
        if ts.is_confirmed:
            row_fill = confirmed_fill
        elif item['warning']:
            row_fill = warning_fill

        for c in range(1, 13):
            cell = ws.cell(row=curr_row, column=c)
            cell.border = cell_border
            cell.alignment = Alignment(horizontal="center" if c > 1 else "left", vertical="center")
            if row_fill:
                cell.fill = row_fill

    # Calculating dynamic width for columns
    for col in ws.columns:
        max_len = 0
        for cell in col:
            val = str(cell.value or '')
            if len(val) > max_len:
                max_len = len(val)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 11)

    # Creating response object
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="pointages_{start_date}_to_{end_date}.xlsx"'
    wb.save(response)
    return response
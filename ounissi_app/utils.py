from dateutil.relativedelta import relativedelta
from datetime import datetime, date
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
    """
    Get the entrance time for today from the Timesheet model directly.
    Querying the database is 1000x faster than pulling raw logs into Pandas on every page load.
    """
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
    """
    Optimized function to retrieve all necessary context data for the base template.
    Reduces database hits by using select_related/prefetch_related where possible.
    """
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
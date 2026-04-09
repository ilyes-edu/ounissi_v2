from zk import ZK, const
import pandas as pd
from accounts.models import Employee
from .models import Timesheet
from django.db import transaction



def import_attendance_logs(device='192.168.1.184', port=4370, timeout=50):
    zk = ZK(device, port=port, timeout=timeout)
    conn = None

    try:
        conn = zk.connect()
        attendance_logs = conn.get_attendance()
        return attendance_logs
    except Exception as e:
        # Handle the connection error
        print(f"Error: {e}")
        return []
    finally:
        if conn:
            conn.disconnect()


# Get attendance logs
def timesheet_dataframe(attendance_logs):
    # 1. Fetch all employees once and map by zk_id
    employees = Employee.objects.all().only('zk_id', 'first_name', 'last_name')
    employee_map = {e.zk_id: f"{e.first_name} {e.last_name}" for e in employees}

    data = []
    for log in attendance_logs:
        zk_id = str(log.user_id)
        employee_name = employee_map.get(zk_id, "inexistant")

        data.append({
            'user_id': zk_id,
            'employee_name': employee_name,
            'timestamp': log.timestamp,
        })

    df = pd.DataFrame(data)
    # Converting timestamp
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    # Extracting date
    df['date'] = df['timestamp'].dt.date
    # Sorting df
    df = df.sort_values(by=['user_id', 'date', 'timestamp'])
    # Removing rows when timestamp diff is less than 10 minute
    df['prev_user_id'] = df['user_id'].shift(1)
    df['prev_date'] = df['date'].shift(1)
    df['time_diff'] = (df['timestamp'] - df['timestamp'].shift(1)).dt.total_seconds() / 60

    df = df[((df['user_id'] != df['prev_user_id']) | (df['date'] != df['prev_date']) | (df['time_diff'] >= 10))]

    # Group by user_id and date, then aggregate timestamps
    # After filtering by time_diff >= 10:
    result = df.groupby(['user_id', 'employee_name', 'date']).agg({
        'timestamp': lambda x: ', '.join(x.dt.strftime('%H:%M:%S'))}).reset_index()

    for i in range(6):
        extracted_times = result['timestamp'].str.split(', ').str[i]
        result[f'timestamp_{i + 1}'] = extracted_times.where(extracted_times.notna(), None)

    return result.drop(columns=['timestamp'])

    return result

def save_logs(result_df):
    # 1. Pre-fetch all relevant employees into a dictionary
    zk_ids = result_df['user_id'].unique()
    employees = {e.zk_id: e for e in Employee.objects.filter(zk_id__in=zk_ids)}

    # 2. Pre-fetch existing timesheets to avoid get_or_create
    dates = result_df['date'].unique()
    existing_timesheets = {
        (str(ts.employee.zk_id), ts.date): ts
        for ts in Timesheet.objects.filter(employee__zk_id__in=zk_ids, date__in=dates)
    }

    new_timesheets = []
    updated_timesheets = []

    for _, row in result_df.iterrows():
        zk_id = str(row['user_id'])
        date = row['date']
        employee = employees.get(zk_id)

        if not employee:
            continue

            # Check if we already have a record for this day
        timesheet = existing_timesheets.get((zk_id, date))

        # PROTECTION: If it exists and is ALREADY confirmed, skip it entirely
        if timesheet and timesheet.is_confirmed:
            continue  # This record is locked by "calcule pointage"

        # Map row values to the correct field names
        data = {
            'start_time': row['timestamp_1'],
            'end_time': row['timestamp_2'],
            'start_time_2': row['timestamp_3'],
            'end_time_2': row['timestamp_4'],
            'start_time_3': row['timestamp_5'],
            'end_time_3': row['timestamp_6'],
        }

        timesheet = existing_timesheets.get((zk_id, date))

        if timesheet:
            # Update existing unconfirmed record
            for key, value in data.items():
                setattr(timesheet, key, value)
            updated_timesheets.append(timesheet)
        else:
            # Create a brand new record
            new_timesheets.append(Timesheet(employee=employee, date=date, **data))

            # 4. Save using Bulk operations for maximum speed
        with transaction.atomic():
            if new_timesheets:
                Timesheet.objects.bulk_create(new_timesheets)
            if updated_timesheets:
                # Only updates the time fields for non-confirmed days
                Timesheet.objects.bulk_update(updated_timesheets, [
                    'start_time', 'end_time', 'start_time_2',
                    'end_time_2', 'start_time_3', 'end_time_3'
                ])
from zk import ZK, const
from datetime import datetime, time
import pandas as pd
import numpy as np
from accounts.models import Employee
from .models import Timesheet
from django.db.models import Q


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
    data = []

    # Create a dictionary to store employee objects by zk_id for reuse
    employee_cache = {}

    for log in attendance_logs:
        zk_id = log.user_id
        if zk_id in employee_cache:
            employee = employee_cache[zk_id]
        else:
            try:
                employee = Employee.objects.get(zk_id=zk_id)
                employee_cache[zk_id] = employee
            except Employee.DoesNotExist:
                employee = None

        if employee:
            employee_name = f"{employee.first_name} {employee.last_name}"
        else:
            employee_name = "inexistant"

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
    result = df.groupby(['user_id', 'employee_name', 'date']).agg({
        'timestamp': lambda x: ', '.join(x.dt.strftime('%H:%M:%S'))}).reset_index()

    # Split the aggregated timestamps into separate columns
    for i in range(6):
        # Use pandas where() or simply replace explicitly without chained fillna warnings
        extracted_times = result['timestamp'].str.split(', ').str[i]
        result[f'timestamp_{i + 1}'] = extracted_times.where(extracted_times.notna(), None)

    result = result.drop(columns=['timestamp'])

    return result


def save_logs(result_df):
    for _, row in result_df.iterrows():
        zk_id = row['user_id']
        date = row['date']

        # Try to get the existing Timesheet record, or create a new one if it doesn't exist
        employee = Employee.objects.get(zk_id=zk_id)

        # Convert timestamps to datetime objects if they are not None
        timestamp_1 = datetime.strptime(str(row['timestamp_1']), '%H:%M:%S') if row['timestamp_1'] else None
        timestamp_2 = datetime.strptime(str(row['timestamp_2']), '%H:%M:%S') if row['timestamp_2'] else None
        timestamp_3 = datetime.strptime(str(row['timestamp_3']), '%H:%M:%S') if row['timestamp_3'] else None
        timestamp_4 = datetime.strptime(str(row['timestamp_4']), '%H:%M:%S') if row['timestamp_4'] else None
        timestamp_5 = datetime.strptime(str(row['timestamp_5']), '%H:%M:%S') if row['timestamp_5'] else None
        timestamp_6 = datetime.strptime(str(row['timestamp_6']), '%H:%M:%S') if row['timestamp_6'] else None

        timesheet, created = Timesheet.objects.get_or_create(
            employee__zk_id=zk_id,  # Match by zk_id
            date=date,
            defaults={
                'employee': employee,
                'start_time': timestamp_1.strftime('%H:%M:%S') if timestamp_1 else None,  # Convert to string or None
                'end_time': timestamp_2.strftime('%H:%M:%S') if timestamp_2 else None,  # Convert to string or None
                'start_time_2': timestamp_3.strftime('%H:%M:%S') if timestamp_3 else None,  # Convert to string or None
                'end_time_2': timestamp_4.strftime('%H:%M:%S') if timestamp_4 else None,  # Convert to string or None
                'start_time_3': timestamp_5.strftime('%H:%M:%S') if timestamp_5 else None,  # Convert to string or None
                'end_time_3': timestamp_6.strftime('%H:%M:%S') if timestamp_6 else None,  # Convert to string or None
            }
        )

        if not created and not timesheet.is_confirmed:
            # If the Timesheet record already exists and is not confirmed, update its fields
            timesheet.start_time = timestamp_1.strftime(
                '%H:%M:%S') if timestamp_1 else None  # Convert to string or None
            timesheet.end_time = timestamp_2.strftime('%H:%M:%S') if timestamp_2 else None  # Convert to string or None
            timesheet.start_time_2 = timestamp_3.strftime(
                '%H:%M:%S') if timestamp_3 else None  # Convert to string or None
            timesheet.end_time_2 = timestamp_4.strftime(
                '%H:%M:%S') if timestamp_4 else None  # Convert to string or None
            timesheet.start_time_3 = timestamp_5.strftime(
                '%H:%M:%S') if timestamp_5 else None  # Convert to string or None
            timesheet.end_time_3 = timestamp_6.strftime(
                '%H:%M:%S') if timestamp_6 else None  # Convert to string or None
            timesheet.save()


from zk import ZK
import pandas as pd
from accounts.models import Employee
from .models import Timesheet
from django.db import transaction
from django.conf import settings


def import_attendance_logs(device=None, port=4370, timeout=50):
    # Use settings if available, otherwise default to your provided IP
    ip = device or getattr(settings, 'ZK_DEVICE_IP', '192.168.1.184')
    zk = ZK(ip, port=port, timeout=timeout)
    conn = None
    try:
        conn = zk.connect()
        return conn.get_attendance()
    except Exception as e:
        print(f"Connection Error: {e}")
        return []
    finally:
        if conn: conn.disconnect()


def timesheet_dataframe(attendance_logs):
    if not attendance_logs: return pd.DataFrame()

    employees = Employee.objects.all().only('zk_id', 'first_name', 'last_name')
    employee_map = {str(e.zk_id): f"{e.first_name} {e.last_name}" for e in employees}

    data = [{
        'user_id': str(log.user_id),
        'employee_name': employee_map.get(str(log.user_id), "inexistant"),
        'timestamp': log.timestamp,
    } for log in attendance_logs]

    df = pd.DataFrame(data)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['date'] = df['timestamp'].dt.date
    df = df.sort_values(by=['user_id', 'date', 'timestamp'])

    # 10-minute noise filter
    df['time_diff'] = (df['timestamp'] - df['timestamp'].shift(1)).dt.total_seconds() / 60
    mask = (df['user_id'] != df['user_id'].shift(1)) | \
           (df['date'] != df['date'].shift(1)) | \
           (df['time_diff'] >= 10)
    df = df[mask]

    # Aggregate to 6 columns
    result = df.groupby(['user_id', 'employee_name', 'date']).agg({
        'timestamp': lambda x: ', '.join(x.dt.strftime('%H:%M:%S'))
    }).reset_index()

    for i in range(6):
        col_name = f'timestamp_{i + 1}'
        result[col_name] = result['timestamp'].str.split(', ').str[i].replace({pd.NA: None})

    return result.drop(columns=['timestamp'])


def save_logs(result_df):
    if result_df.empty: return

    zk_ids = result_df['user_id'].unique()
    employees = {str(e.zk_id): e for e in Employee.objects.filter(zk_id__in=zk_ids)}

    dates = result_df['date'].unique()
    existing_ts = {
        (str(ts.employee.zk_id), ts.date): ts
        for ts in Timesheet.objects.filter(employee__zk_id__in=zk_ids, date__in=dates)
    }

    new_timesheets = []
    updated_timesheets = []

    for _, row in result_df.iterrows():
        zk_id = str(row['user_id'])
        date = row['date']
        employee = employees.get(zk_id)
        if not employee: continue

        timesheet = existing_ts.get((zk_id, date))
        if timesheet and timesheet.is_confirmed:
            continue

        data = {
            'start_time': row['timestamp_1'],
            'end_time': row['timestamp_2'],
            'start_time_2': row['timestamp_3'],
            'end_time_2': row['timestamp_4'],
            'start_time_3': row['timestamp_5'],
            'end_time_3': row['timestamp_6'],
        }

        if timesheet:
            for key, val in data.items(): setattr(timesheet, key, val)
            updated_timesheets.append(timesheet)
        else:
            new_timesheets.append(Timesheet(employee=employee, date=date, **data))

    # CRITICAL: Bulk operations MUST be outside the loop
    with transaction.atomic():
        if new_timesheets:
            Timesheet.objects.bulk_create(new_timesheets)
        if updated_timesheets:
            Timesheet.objects.bulk_update(updated_timesheets, [
                'start_time', 'end_time', 'start_time_2',
                'end_time_2', 'start_time_3', 'end_time_3'
            ])
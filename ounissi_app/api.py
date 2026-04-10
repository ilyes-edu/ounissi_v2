from django.utils import timezone
from ninja import NinjaAPI, Schema
from typing import List, Optional
from .models import Timesheet, UserSyncLog
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.contrib.auth.decorators import login_required

# Initialize API
ninja_api = NinjaAPI()

# 1. Define what a single row update looks like
class TimesheetRowSchema(Schema):
    id: int
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    start_time_2: Optional[str] = None
    end_time_2: Optional[str] = None
    start_time_3: Optional[str] = None
    end_time_3: Optional[str] = None


# 2. The Bulk Update Endpoint
@ninja_api.post("/timesheets/bulk-validate")
def bulk_update_timesheets(request, data: List[TimesheetRowSchema]):
    updated_count = 0

    with transaction.atomic():
        for entry in data:
            # Fetch the record
            ts = get_object_or_404(Timesheet, id=entry.id)

            # Update fields (empty strings from JS inputs become None)
            ts.start_time = entry.start_time or None
            ts.end_time = entry.end_time or None
            ts.start_time_2 = entry.start_time_2 or None
            ts.end_time_2 = entry.end_time_2 or None
            ts.start_time_3 = entry.start_time_3 or None
            ts.end_time_3 = entry.end_time_3 or None

            # Business Logic: Auto-confirm upon validation
            ts.is_confirmed = True
            ts.save()
            updated_count += 1

    return {"status": "success", "message": f"Validated {updated_count} lines successfully."}


@ninja_api.post("/timesheets/sync-my-data")
def sync_my_data(request):
    user = request.user
    today = timezone.localtime().date()

    # 1. Quota Check
    sync_record, _ = UserSyncLog.objects.get_or_create(user=user, date=today)

    if sync_record.count >= 3:
        return {"status": "error", "message": "Quota quotidien atteint (3/3). Réessayez demain."}

    # 2. Trigger the ZKTeco Sync (Assuming the function is import_from_zkteco)
    try:
        from .utils import import_from_zkteco
        import_from_zkteco()  # This updates the DB with the latest logs

        # 3. Increment the counter
        sync_record.count += 1
        sync_record.save()

        return {
            "status": "success",
            "message": f"Synchronisation réussie. Quota restant: {3 - sync_record.count}"
        }
    except Exception as e:
        return {"status": "error", "message": f"Erreur terminal: {str(e)}"}
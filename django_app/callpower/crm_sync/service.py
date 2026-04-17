from django.db import transaction
from django.utils import timezone

from callpower.apps.core.models import Call, SyncCall
from callpower.crm_sync.integrations import get_crm_integration
from callpower.crm_sync.integrations.base import CRMIntegrationError, safe_twilio_lookup


@transaction.atomic
def sync_campaign_calls(sync_campaign):
    integration = get_crm_integration()
    unsynced_calls = (
        Call.objects.filter(campaign=sync_campaign.campaign)
        .exclude(sync_records__isnull=False)
        .select_related("campaign", "target", "session")
        .order_by("timestamp", "id")
    )

    attempted = 0
    saved = 0
    skipped = 0

    for call in unsynced_calls:
        if call.sync_records.exists():
            continue
        attempted += 1
        success, sync_call = sync_single_call(sync_campaign, call, integration)
        if success:
            saved += 1
            if integration.BATCH_ALL_CALLS_IN_SESSION and call.session_id:
                sibling_calls = (
                    Call.objects.filter(session_id=call.session_id, campaign=sync_campaign.campaign)
                    .exclude(id=call.id)
                    .exclude(sync_records__isnull=False)
                )
                for sibling in sibling_calls:
                    SyncCall.objects.create(
                        call=sibling,
                        saved=False,
                        crm_message=f"batched with call {call.id}",
                    )
                    skipped += 1

    completed_calls = Call.objects.filter(campaign=sync_campaign.campaign, status="completed").count()
    try:
        integration.save_campaign_meta(sync_campaign.crm_id, {"count": completed_calls})
    except NotImplementedError:
        pass

    sync_campaign.last_sync_time = timezone.now()
    sync_campaign.save(update_fields=["last_sync_time"])
    return {"attempted": attempted, "saved": saved, "skipped": skipped}


def sync_single_call(sync_campaign, call, integration):
    if not call.call_id:
        return False, None
    try:
        user_phone = safe_twilio_lookup(integration, call.call_id)
    except CRMIntegrationError:
        return False, None
    if not user_phone:
        return False, None

    crm_user = integration.get_user(user_phone)
    if not crm_user:
        return False, None

    saved, message = integration.save_action(call, sync_campaign.crm_id, crm_user, sync_campaign.crm_key)
    if saved:
        sync_call = SyncCall.objects.create(call=call, saved=True, crm_message=message or "")
        return True, sync_call
    return False, None

from __future__ import annotations

import json
from typing import Iterable

from django.test import RequestFactory
from django.utils import timezone

from callpower.apps.calls.views import create as create_call_view
from callpower.apps.core.models import ScheduleCall, ScheduledJob, SyncCampaign, next_sync_run, next_weekday_run
from callpower.crm_sync.service import sync_campaign_calls


def due_jobs(now=None) -> Iterable[ScheduledJob]:
    now = now or timezone.now()
    return ScheduledJob.objects.filter(active=True, next_run_at__isnull=False, next_run_at__lte=now).order_by(
        "next_run_at", "id"
    )


def run_due_jobs(now=None):
    now = now or timezone.now()
    results = []
    for job in due_jobs(now):
        if job.kind == ScheduledJob.KIND_SCHEDULED_CALL:
            results.append(run_scheduled_call_job(job, now))
        elif job.kind == ScheduledJob.KIND_CRM_SYNC:
            results.append(run_crm_sync_job(job, now))
    return results


def run_scheduled_call_job(job, now=None):
    now = now or timezone.now()
    schedule_call = ScheduleCall.objects.filter(pk=job.object_id).select_related("campaign").first()
    if not schedule_call:
        job.active = False
        job.save(update_fields=["active"])
        return {"job": job.job_key, "kind": job.kind, "status": "missing"}

    if not schedule_call.subscribed:
        job.active = False
        job.save(update_fields=["active"])
        return {"job": job.job_key, "kind": job.kind, "status": "unsubscribed"}

    campaign = schedule_call.campaign
    executed = False
    result_payload = {}

    if campaign and campaign.status_code == 2:
        factory = RequestFactory()
        payload = {
            "campaignId": str(campaign.id),
            "userPhone": schedule_call.phone_number or "",
            "userCountry": (campaign.country_code or "US").upper(),
            "userLocation": (job.payload or {}).get("location", ""),
            "scheduled": "true",
        }
        request = factory.post("/call/create", data=payload)
        request.META["REMOTE_ADDR"] = "127.0.0.1"
        response = create_call_view(request)
        try:
            result_payload = json.loads(response.content.decode("utf-8"))
        except Exception:
            result_payload = {"status_code": response.status_code}
        if response.status_code == 200 and result_payload.get("call") != "failed":
            schedule_call.last_called = now
            schedule_call.num_calls = (schedule_call.num_calls or 0) + 1
            schedule_call.save(update_fields=["last_called", "num_calls"])
            executed = True

    schedule_call_time = schedule_call.time_to_call or now.time().replace(second=0, microsecond=0)
    job.last_run_at = now
    job.next_run_at = next_weekday_run(schedule_call_time, now)
    job.save(update_fields=["last_run_at", "next_run_at"])
    return {
        "job": job.job_key,
        "kind": job.kind,
        "status": "executed" if executed else "skipped",
        "details": result_payload,
    }


def run_crm_sync_job(job, now=None):
    now = now or timezone.now()
    sync_campaign = SyncCampaign.objects.filter(pk=job.object_id).select_related("campaign").first()
    if not sync_campaign:
        job.active = False
        job.save(update_fields=["active"])
        return {"job": job.job_key, "kind": job.kind, "status": "missing"}

    result = sync_campaign_calls(sync_campaign)

    job.last_run_at = now
    job.next_run_at = next_sync_run(sync_campaign.schedule, now)
    job.save(update_fields=["last_run_at", "next_run_at"])
    return {
        "job": job.job_key,
        "kind": job.kind,
        "status": "executed",
        "details": result,
    }

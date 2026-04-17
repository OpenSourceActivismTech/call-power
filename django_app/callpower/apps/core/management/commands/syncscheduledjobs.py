from django.core.management.base import BaseCommand

from callpower.apps.core.models import ScheduleCall, SyncCampaign


class Command(BaseCommand):
    help = "Backfill Django scheduler metadata from existing scheduled call and sync records."

    def handle(self, *args, **options):
        scheduled_call_count = 0
        sync_campaign_count = 0

        for schedule_call in ScheduleCall.objects.filter(subscribed=True).order_by("id"):
            schedule_call.start_job()
            scheduled_call_count += 1

        for sync_campaign in SyncCampaign.objects.exclude(schedule__isnull=True).exclude(schedule="").order_by("id"):
            if sync_campaign.has_schedule():
                sync_campaign.start(sync_campaign.schedule)
                sync_campaign_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Synced {scheduled_call_count} scheduled calls and {sync_campaign_count} CRM sync schedules."
            )
        )

from django.core.management.base import BaseCommand, CommandError

from callpower.apps.core.models import SyncCampaign
from callpower.crm_sync.service import sync_campaign_calls


class Command(BaseCommand):
    help = "Run CRM sync for one campaign or all configured sync campaigns."

    def add_arguments(self, parser):
        parser.add_argument("campaigns", nargs="?", default="all")

    def handle(self, *args, **options):
        campaign_arg = options["campaigns"]
        if campaign_arg == "all":
            sync_campaigns = SyncCampaign.objects.select_related("campaign").all()
        elif "," in campaign_arg:
            ids = [value.strip() for value in campaign_arg.split(",") if value.strip()]
            sync_campaigns = SyncCampaign.objects.select_related("campaign").filter(campaign_id__in=ids)
        else:
            sync_campaigns = SyncCampaign.objects.select_related("campaign").filter(campaign_id=campaign_arg)

        if not sync_campaigns:
            raise CommandError("No matching sync campaigns found.")

        for sync_campaign in sync_campaigns:
            result = sync_campaign_calls(sync_campaign)
            self.stdout.write(
                self.style.SUCCESS(
                    f"campaign {sync_campaign.campaign_id}: attempted={result['attempted']} saved={result['saved']} skipped={result['skipped']}"
                )
            )

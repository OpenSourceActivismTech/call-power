from django.core.management.base import BaseCommand

from ._legacy_helpers import restart_scheduled_calls


class Command(BaseCommand):
    help = "Rebind subscribed scheduled calls for one campaign or all live scheduled campaigns."

    def add_arguments(self, parser):
        parser.add_argument("campaign_id")
        parser.add_argument("--accept-all", action="store_true", dest="accept_all")

    def handle(self, *args, **options):
        updated = restart_scheduled_calls(
            options["campaign_id"],
            accept_all=options["accept_all"],
        )
        for campaign, scheduled_calls in updated:
            self.stdout.write(f"Scheduled calls for {campaign.name}: {len(scheduled_calls)}")
        self.stdout.write(self.style.SUCCESS("Scheduled calls rebound into the Django scheduler."))

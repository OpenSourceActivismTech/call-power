from datetime import date

from django.core.management.base import BaseCommand

from ._legacy_helpers import stop_scheduled_calls


class Command(BaseCommand):
    help = "Unsubscribe scheduled calls created before a date."

    def add_arguments(self, parser):
        parser.add_argument("campaign_id", type=int)
        parser.add_argument("date", nargs="?", default=date.today().isoformat())
        parser.add_argument("--accept-all", action="store_true", dest="accept_all")

    def handle(self, *args, **options):
        campaign, scheduled_calls = stop_scheduled_calls(
            options["campaign_id"],
            options["date"],
            accept_all=options["accept_all"],
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Stopped {len(scheduled_calls)} scheduled calls for campaign {campaign.id} ({campaign.name})."
            )
        )

from django.core.management.base import BaseCommand

from ._legacy_helpers import fix_targets


class Command(BaseCommand):
    help = "Deduplicate a campaign's targets and recreate campaign target links."

    def add_arguments(self, parser):
        parser.add_argument("campaign_id", type=int)

    def handle(self, *args, **options):
        campaign, created_links = fix_targets(options["campaign_id"], self.stdout)
        self.stdout.write(
            self.style.SUCCESS(f"Rebuilt {created_links} target links for campaign {campaign.id} ({campaign.name}).")
        )

from django.core.management.base import BaseCommand

from ._legacy_helpers import load_political_data


class Command(BaseCommand):
    help = "Load political data into the Django-backed cache."

    def handle(self, *args, **options):
        total = load_political_data(self.stdout)
        self.stdout.write(self.style.SUCCESS(f"Loaded {total} political data objects."))

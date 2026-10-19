from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Clear the Django cache store used by the migrated app."

    def add_arguments(self, parser):
        parser.add_argument("--accept-all", action="store_true", dest="accept_all")

    def handle(self, *args, **options):
        if not options["accept_all"]:
            raise CommandError("This command requires --accept-all in the Django migration.")
        cache.clear()
        self.stdout.write(self.style.SUCCESS("Django cache cleared."))

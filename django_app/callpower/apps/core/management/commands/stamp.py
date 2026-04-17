from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Compatibility shim for the legacy Alembic stamp command."

    def add_arguments(self, parser):
        parser.add_argument("revision")

    def handle(self, *args, **options):
        raise CommandError(
            "Alembic revision stamping is not part of the Django migration path. "
            "Use Django's built-in migration commands for managed apps."
        )

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Compatibility shim for the legacy Flask/Alembic migration generator."

    def add_arguments(self, parser):
        parser.add_argument("message")

    def handle(self, *args, **options):
        raise CommandError(
            "The legacy Alembic `migration` command is not used in the Django stack. "
            "Use `python3 manage.py makemigrations` for managed Django apps, or edit the legacy schema directly "
            "only when you intentionally keep these tables unmanaged."
        )

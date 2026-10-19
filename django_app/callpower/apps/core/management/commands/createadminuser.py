from django.core.management.base import BaseCommand

from ._legacy_helpers import create_admin_user


class Command(BaseCommand):
    help = "Create a legacy admin user that can sign into the Django-migrated admin."

    def add_arguments(self, parser):
        parser.add_argument("--username", default=None)
        parser.add_argument("--password", default=None)
        parser.add_argument("--email", default=None)

    def handle(self, *args, **options):
        user = create_admin_user(
            username=options["username"],
            password=options["password"],
            email=options["email"],
        )
        self.stdout.write(self.style.SUCCESS(f"created admin user {user.name}"))

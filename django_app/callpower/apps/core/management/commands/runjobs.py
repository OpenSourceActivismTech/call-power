from time import sleep

from django.core.management.base import BaseCommand

from callpower.apps.core.scheduler import run_due_jobs


class Command(BaseCommand):
    help = "Run due Django-managed recurring jobs for scheduled calls and CRM sync."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")
        parser.add_argument("--poll-seconds", type=int, default=15, dest="poll_seconds")

    def handle(self, *args, **options):
        once = options["once"]
        poll_seconds = max(1, options["poll_seconds"])

        while True:
            results = run_due_jobs()
            for result in results:
                self.stdout.write(f"{result['kind']} {result['job']}: {result['status']}")
            if once:
                return
            sleep(poll_seconds)

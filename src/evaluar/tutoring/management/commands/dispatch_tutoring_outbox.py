from django.core.management.base import BaseCommand

from evaluar.tutoring.queue import CloudTasksDispatcher, dispatch_pending


class Command(BaseCommand):
    help = "Dispatch pending tutoring outbox events to Cloud Tasks."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        dispatched = dispatch_pending(CloudTasksDispatcher.from_settings(), limit=options["limit"])
        self.stdout.write(self.style.SUCCESS(f"Dispatched {dispatched} tutoring task(s)."))

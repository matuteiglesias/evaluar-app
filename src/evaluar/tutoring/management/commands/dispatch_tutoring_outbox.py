import time

from django.core.management.base import BaseCommand

from evaluar.tutoring.queue import CloudTasksDispatcher, dispatch_pending


class Command(BaseCommand):
    help = "Dispatch pending tutoring outbox events to Cloud Tasks."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--watch", action="store_true")
        parser.add_argument("--interval", type=float, default=60)

    def handle(self, *args, **options):
        dispatcher = CloudTasksDispatcher.from_settings()
        while True:
            dispatched = dispatch_pending(dispatcher, limit=options["limit"])
            self.stdout.write(self.style.SUCCESS(f"Dispatched {dispatched} tutoring task(s)."))
            if not options["watch"]:
                return
            time.sleep(options["interval"])

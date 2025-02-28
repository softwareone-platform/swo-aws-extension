from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Demo command"

    def success(self, message):
        self.stdout.write(self.style.SUCCESS(message), ending="\n")

    def info(self, message):
        self.stdout.write(message, ending="\n")

    def warning(self, message):
        self.stdout.write(self.style.WARNING(message), ending="\n")

    def error(self, message):
        self.stderr.write(self.style.ERROR(message), ending="\n")

    def handle(self, *args, **options):
        self.success("Success message")
        self.info("Info message")
        self.warning("Warning message")
        self.error("Error message")



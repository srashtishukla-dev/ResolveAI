from django.core.management.base import BaseCommand

from ai_engine.services import train_classifier


class Command(BaseCommand):
    help = 'Train and save the synthetic ticket category classifier.'

    def handle(self, *args, **options):
        output_path = train_classifier()
        self.stdout.write(
            self.style.SUCCESS(f'Ticket category model saved to {output_path}')
        )

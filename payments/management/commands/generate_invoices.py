from django.core.management.base import BaseCommand, CommandError

from payments.models import Fee
from payments.services import generate_invoices_for_fee


class Command(BaseCommand):
    help = "Generate one invoice per active member for a given fee."

    def add_arguments(self, parser):
        parser.add_argument("--fee", type=int, required=True)

    def handle(self, *args, **options):
        fee = Fee.objects.filter(pk=options["fee"]).first()
        if fee is None:
            raise CommandError(f"Fee {options['fee']} does not exist.")
        created = generate_invoices_for_fee(fee)
        self.stdout.write(
            self.style.SUCCESS(
                f"Created {len(created)} invoices for '{fee}' "
                f"(total invoices for this fee: {fee.invoices.count()})."
            )
        )

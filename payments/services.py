from people.models import Membership, Person

from .models import Invoice


def generate_invoices_for_fee(fee):
    members = Person.objects.filter(
        club=fee.club,
        membership__status=Membership.Status.ACTIVE,
    ).exclude(membership__isnull=True)
    created = []
    for person in members.order_by("last_name", "first_name"):
        invoice, was_created = Invoice.objects.get_or_create(
            club=fee.club,
            person=person,
            fee=fee,
            defaults={
                "season": fee.season,
                "title": fee.name,
                "amount": fee.amount,
                "due_date": fee.season.end_date if fee.season else None,
            },
        )
        if was_created:
            created.append(invoice)
    return created

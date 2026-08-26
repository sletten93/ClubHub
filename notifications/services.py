from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from groups.models import GroupMembership
from people.models import Membership, Person

from .models import NotificationRecipient


def render_body(body, person):
    return (
        body.replace("{{first_name}}", person.first_name)
        .replace("{{last_name}}", person.last_name)
    )


def resolve_recipients(notification):
    ids = set()
    if notification.all_members:
        ids |= set(
            Person.objects.filter(
                club=notification.club,
                membership__status=Membership.Status.ACTIVE,
            ).values_list("id", flat=True)
        )
    ids |= set(
        GroupMembership.objects.filter(
            group__in=notification.groups.all(),
            role=GroupMembership.Role.MEMBER,
            left_on__isnull=True,
        ).values_list("person_id", flat=True)
    )
    return Person.objects.filter(id__in=ids).order_by("last_name", "first_name")


def register_recipients(notification):
    recipients = []
    for person in resolve_recipients(notification):
        recipient, _ = NotificationRecipient.objects.get_or_create(
            notification=notification, person=person
        )
        recipients.append(recipient)
    return recipients


def send_notification(notification):
    sent = 0
    for recipient in notification.recipients.select_related("person"):
        person = recipient.person
        if not person.email:
            recipient.error = "No email address on file."
            recipient.save()
            continue
        try:
            send_mail(
                notification.subject,
                render_body(notification.body, person),
                settings.DEFAULT_FROM_EMAIL,
                [person.email],
            )
            recipient.sent_at = timezone.now()
            recipient.error = ""
            sent += 1
        except Exception as exc:
            recipient.error = str(exc)[:500]
        recipient.save()
    if notification.sent_at is None:
        notification.sent_at = timezone.now()
        notification.save(update_fields=["sent_at"])
    return sent

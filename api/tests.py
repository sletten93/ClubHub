from datetime import date, time
from decimal import Decimal

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from attendance.models import AttendanceRecord
from clubs.models import Club
from groups.models import Group, GroupMembership
from notifications.models import Notification
from notifications.services import register_recipients, resolve_recipients, send_notification
from payments.models import Fee, Invoice, Payment
from payments.services import generate_invoices_for_fee
from people.models import Membership, Person, StaffProfile
from people.tests import complete_pnr
from scheduling.models import Activity, ActivityType, Season


class PaymentsTests(TestCase):
    def setUp(self):
        self.club = Club.objects.create(name="Pay BK", slug="paybk")
        self.season = Season.objects.create(
            club=self.club,
            name="Vår 2026",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
        )
        self.fee = Fee.objects.create(
            club=self.club, name="Träningsavgift", amount=Decimal("1200.00"), season=self.season
        )
        self.active = self._member("Active One", "900101123", Membership.Status.ACTIVE)
        self.inactive = self._member("Inactive Two", "850505123", Membership.Status.INACTIVE)

    def _member(self, name, nine_digits, status):
        first, last = name.split()
        person = Person.objects.create(
            club=self.club,
            first_name=first,
            last_name=last,
            personnummer=complete_pnr(nine_digits),
            gender=Person.Gender.FEMALE,
            street_address="Gatan 1",
            postal_code="11122",
            city="Stockholm",
        )
        Membership.objects.create(person=person, start_date=date(2026, 1, 1), status=status)
        return person

    def test_generate_invoices_skips_inactive_and_is_idempotent(self):
        created = generate_invoices_for_fee(self.fee)
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].person, self.active)
        again = generate_invoices_for_fee(self.fee)
        self.assertEqual(again, [])
        self.assertEqual(Invoice.objects.count(), 1)

    def test_payment_updates_status_progressively(self):
        generate_invoices_for_fee(self.fee)
        invoice = Invoice.objects.get(person=self.active)
        self.assertEqual(invoice.status, Invoice.Status.UNPAID)
        Payment.objects.create(invoice=invoice, amount=Decimal("500.00"))
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PARTLY_PAID)
        Payment.objects.create(invoice=invoice, amount=Decimal("700.00"))
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PAID)

    def test_invoice_list_requires_admin(self):
        trainer = Person.objects.create(
            club=self.club,
            first_name="Erik",
            last_name="Trainer",
            personnummer=complete_pnr("870512123"),
            gender=Person.Gender.MALE,
            street_address="Gatan 1",
            postal_code="11122",
            city="Stockholm",
        )
        StaffProfile.objects.create(person=trainer)
        user = User.objects.create_user(username="tr", password="pw12345!")
        trainer.user = user
        trainer.save()
        self.client.force_login(user)
        response = self.client.get(reverse("payments:list"))
        self.assertEqual(response.status_code, 403)


class NotificationsTests(TestCase):
    def setUp(self):
        self.club = Club.objects.create(name="Notis BK", slug="notisbk")
        self.member = self._person("Mona", "Member", "900303123")
        self.no_email = self._person("Nils", "Noemail", "870512123", email="")
        self.group = Group.objects.create(club=self.club, name="Juniorer")
        for person in (self.member, self.no_email):
            GroupMembership.objects.create(group=self.group, person=person)

    def _person(self, first_name, last_name, nine_digits, email="x@example.com"):
        person = Person.objects.create(
            club=self.club,
            first_name=first_name,
            last_name=last_name,
            personnummer=complete_pnr(nine_digits),
            gender=Person.Gender.FEMALE,
            street_address="Gatan 1",
            postal_code="11122",
            city="Stockholm",
            email=email,
        )
        Membership.objects.create(person=person, start_date=date(2026, 1, 1))
        return person

    def _notification(self, **kwargs):
        defaults = dict(
            club=self.club,
            subject="Hej",
            body="Hej {{first_name}}, vi tränar som vanligt.",
            all_members=True,
        )
        defaults.update(kwargs)
        return Notification.objects.create(**defaults)

    def test_send_personalizes_and_reports_errors(self):
        notification = self._notification()
        register_recipients(notification)
        sent = send_notification(notification)
        self.assertEqual(sent, 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Hej Mona", mail.outbox[0].body)
        failed = notification.recipients.get(person=self.no_email)
        self.assertFalse(failed.sent_at)
        self.assertTrue(failed.error)

    def test_group_audience_respects_role_and_left_members(self):
        coach = self._person("Erik", "Coach", "830505123")
        left_member = self._person("Gone", "Girl", "800101123")
        GroupMembership.objects.create(
            group=self.group, person=coach, role=GroupMembership.Role.TRAINER
        )
        membership = GroupMembership.objects.create(group=self.group, person=left_member)
        membership.left_on = date(2026, 2, 1)
        membership.save()
        notification = self._notification(all_members=False)
        notification.groups.add(self.group)
        recipients = resolve_recipients(notification)
        self.assertEqual(
            set(recipients), {self.member, self.no_email}
        )


class ScheduleAPITests(TestCase):
    def setUp(self):
        self.club = Club.objects.create(name="API BK", slug="apibk")
        self.season = Season.objects.create(
            club=self.club,
            name="Vår 2026",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
        )
        self.group = Group.objects.create(club=self.club, name="Juniorer")

    def _activity(self, day, title="Träning"):
        return Activity.objects.create(
            club=self.club,
            season=self.season,
            group=self.group,
            title=title,
            activity_type=ActivityType.TRAINING,
            date=day,
            start_time=time(17, 0),
            end_time=time(18, 0),
        )

    def test_schedule_within_window(self):
        inside = self._activity(date(2026, 3, 10))
        outside = self._activity(date(2030, 3, 10))
        cancelled = self._activity(date(2026, 3, 11))
        cancelled.is_cancelled = True
        cancelled.save()

        url = reverse("api:club_schedule", kwargs={"slug": self.club.slug})
        response = self.client.get(url, {"from": "2026-03-01", "to": "2026-03-31"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 2)
        ids = {row["id"] for row in data}
        self.assertIn(inside.pk, ids)
        self.assertNotIn(outside.pk, ids)
        cancelled_row = next(row for row in data if row["id"] == cancelled.pk)
        self.assertTrue(cancelled_row["is_cancelled"])
        self.assertEqual(cancelled_row["group"]["name"], "Juniorer")

    def test_unknown_club_404(self):
        url = reverse("api:club_schedule", kwargs={"slug": "missing"})
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_invalid_range_400(self):
        url = reverse("api:club_schedule", kwargs={"slug": self.club.slug})
        response = self.client.get(url, {"from": "2026-03-31", "to": "2026-03-01"})
        self.assertEqual(response.status_code, 400)

    def test_groups_endpoint(self):
        url = reverse("api:club_groups", kwargs={"slug": self.club.slug})
        data = self.client.get(url).json()
        self.assertEqual(data, [{"id": self.group.pk, "name": "Juniorer"}])

from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from attendance.models import AttendanceRecord
from clubs.models import Club
from groups.models import Group, GroupMembership
from people.models import GuardianRelation, Membership, Person, StaffProfile
from people.personnummer import _luhn
from payments.models import Fee, Invoice, Payment
from payments.services import generate_invoices_for_fee
from scheduling.models import Activity, ActivityTemplate, ActivityType, Season, Weekday
from scheduling.services import generate_occurrences


def valid_pnr(nine_digits):
    for digit in range(10):
        candidate = f"{nine_digits}{digit}"
        if _luhn(candidate):
            return candidate
    raise RuntimeError("No valid checksum digit")


class Command(BaseCommand):
    help = "Seed the database with demo data for a boxing club."

    def handle(self, *args, **options):
        today = timezone.localdate()

        club, created = Club.objects.get_or_create(
            slug="demo-boxning",
            defaults={
                "name": "Demo Boxningsklubb",
                "city": "Göteborg",
                "email": "info@demoboxning.se",
            },
        )
        if created:
            club.primary_color = "#d92b2b"
            club.secondary_color = "#1f1f1f"
            club.save()

        def make_person(first_name, last_name, nine_digits, gender, email=""):
            person, _ = Person.objects.get_or_create(
                club=club,
                first_name=first_name,
                last_name=last_name,
                defaults={
                    "personnummer": valid_pnr(nine_digits),
                    "gender": gender,
                    "street_address": "Idrottsvägen 1",
                    "postal_code": "41122",
                    "city": "Göteborg",
                    "email": email,
                    "phone_mobile": "070-123 45 67",
                },
            )
            return person

        anna = make_person("Anna", "Ekström", "850101123", Person.Gender.FEMALE, "anna@demo.se")
        erik = make_person("Erik", "Hallberg", "830505123", Person.Gender.MALE, "erik@demo.se")
        sara = make_person("Sara", "Lindqvist", "900303123", Person.Gender.FEMALE, "sara@demo.se")
        johan = make_person("Johan", "Berg", "790707123", Person.Gender.MALE)
        pernilla = make_person("Pernilla", "Nyström", "821212123", Person.Gender.FEMALE, "pernilla@demo.se")
        henrik = make_person("Henrik", "Sandberg", "801010123", Person.Gender.MALE)
        oscar = make_person("Oscar", "Nyström", "160310123", Person.Gender.MALE)
        elsa = make_person("Elsa", "Sandberg", "170505123", Person.Gender.FEMALE)

        GuardianRelation.objects.get_or_create(guardian=pernilla, child=oscar)
        GuardianRelation.objects.get_or_create(guardian=henrik, child=elsa)

        for member in (anna, erik, sara, johan, oscar, elsa):
            Membership.objects.get_or_create(
                person=member,
                defaults={"start_date": today - timedelta(days=100)},
            )

        anna_profile, _ = StaffProfile.objects.get_or_create(person=anna)
        anna_profile.is_admin = True
        anna_profile.save()
        StaffProfile.objects.get_or_create(person=erik)
        StaffProfile.objects.get_or_create(person=sara)

        admin_user, _ = User.objects.get_or_create(username="admin")
        admin_user.set_password("demo1234!")
        admin_user.save()
        anna.user = admin_user
        anna.save()

        trainer_user, _ = User.objects.get_or_create(username="trainer")
        trainer_user.set_password("demo1234!")
        trainer_user.save()
        erik.user = trainer_user
        erik.save()

        juniors, _ = Group.objects.get_or_create(club=club, name="Juniorer")
        seniors, _ = Group.objects.get_or_create(club=club, name="Seniorer")

        def enroll(group, person, role):
            GroupMembership.objects.get_or_create(
                group=group, person=person, defaults={"role": role}
            )

        for kid in (oscar, elsa):
            enroll(juniors, kid, GroupMembership.Role.MEMBER)
        enroll(juniors, erik, GroupMembership.Role.TRAINER)
        enroll(seniors, johan, GroupMembership.Role.MEMBER)
        enroll(seniors, sara, GroupMembership.Role.MEMBER)
        enroll(seniors, sara, GroupMembership.Role.TRAINER)
        enroll(seniors, erik, GroupMembership.Role.TRAINER)

        season, _ = Season.objects.get_or_create(
            club=club,
            name=f"Säsong {today.year}",
            defaults={
                "start_date": today - timedelta(days=30),
                "end_date": today + timedelta(days=150),
            },
        )

        def make_template(title, group, weekday, start, end, location):
            template, created = ActivityTemplate.objects.get_or_create(
                season=season,
                title=title,
                group=group,
                defaults={
                    "club": club,
                    "activity_type": ActivityType.TRAINING,
                    "recurrence": ActivityTemplate.Recurrence.WEEKLY,
                    "weekday": weekday,
                    "start_time": start,
                    "end_time": end,
                    "location": location,
                },
            )
            if created:
                generate_occurrences(template)

        make_template("Juniorträning", juniors, Weekday.MONDAY, time(17, 0), time(18, 30), "Ringen 1")
        make_template("Juniorträning", juniors, Weekday.WEDNESDAY, time(17, 0), time(18, 30), "Ringen 1")
        make_template("Seniorträning", seniors, Weekday.TUESDAY, time(19, 0), time(20, 30), "Ringen 2")
        make_template("Seniorträning", seniors, Weekday.THURSDAY, time(19, 0), time(20, 30), "Ringen 2")

        last_junior = (
            Activity.objects.filter(group=juniors, date__lt=today)
            .order_by("-date")
            .first()
        )
        if last_junior:
            for kid in (oscar, elsa):
                AttendanceRecord.objects.get_or_create(
                    activity=last_junior,
                    person=kid,
                    defaults={
                        "status": AttendanceRecord.Status.PRESENT,
                        "registered_by": erik,
                    },
                )

        fee, _ = Fee.objects.get_or_create(
            club=club,
            name="Träningsavgift",
            defaults={
                "amount": Decimal("1200.00"),
                "season": season,
                "description": "Träningsavgift för säsongen",
            },
        )
        generate_invoices_for_fee(fee)
        johan_invoice = Invoice.objects.filter(person=johan, fee=fee).first()
        if johan_invoice and not johan_invoice.payments.exists():
            Payment.objects.create(
                invoice=johan_invoice,
                amount=johan_invoice.amount,
                method=Payment.Method.SWISH,
                registered_by=anna,
                note="Swish demo",
            )

        self.stdout.write(self.style.SUCCESS(f"Seeded club '{club.name}'."))
        self.stdout.write("Log in as: admin / demo1234! (Anna, club admin)")
        self.stdout.write("           trainer / demo1234! (Erik, trainer)")

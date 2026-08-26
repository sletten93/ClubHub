from datetime import date
from datetime import time as datetime_time

from django.test import TestCase

from clubs.models import Club
from groups.models import Group
from people.models import Person
from people.tests import complete_pnr

from .models import Activity, ActivityTemplate, ActivityType, Season, Weekday
from .services import generate_occurrences, regenerate_occurrences


class OccurrenceGenerationTests(TestCase):
    def setUp(self):
        self.club = Club.objects.create(name="Test BK", slug="testbk")
        self.season = Season.objects.create(
            club=self.club,
            name="Vår 2026",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
        )
        self.group = Group.objects.create(club=self.club, name="Juniorer")

    def make_template(self, **kwargs):
        defaults = dict(
            club=self.club,
            season=self.season,
            group=self.group,
            title="Träning",
            activity_type=ActivityType.TRAINING,
            recurrence=ActivityTemplate.Recurrence.WEEKLY,
            weekday=Weekday.MONDAY,
            start_date=date(2026, 1, 1),
            start_time=datetime_time(18, 0),
            end_time=datetime_time(19, 30),
        )
        defaults.update(kwargs)
        return ActivityTemplate.objects.create(**defaults)

    def test_weekly_generation(self):
        template = self.make_template()
        created = generate_occurrences(template)
        mondays = [
            date(2026, 1, 5), date(2026, 1, 12), date(2026, 1, 19), date(2026, 1, 26),
            date(2026, 2, 2), date(2026, 2, 9), date(2026, 2, 16), date(2026, 2, 23),
            date(2026, 3, 2), date(2026, 3, 9), date(2026, 3, 16), date(2026, 3, 23),
            date(2026, 3, 30),
        ]
        self.assertEqual([activity.date for activity in created], mondays)
        self.assertEqual(Activity.objects.count(), 13)

    def test_generation_is_idempotent(self):
        template = self.make_template()
        generate_occurrences(template)
        second_pass = generate_occurrences(template)
        self.assertEqual(second_pass, [])
        self.assertEqual(Activity.objects.count(), 13)

    def test_single_occurrence_when_no_recurrence(self):
        template = self.make_template(
            recurrence=ActivityTemplate.Recurrence.NONE,
            end_date=date(2026, 1, 10),
        )
        created = generate_occurrences(template)
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0].date, date(2026, 1, 1))

    def test_weekday_generation(self):
        template = self.make_template(
            recurrence=ActivityTemplate.Recurrence.WEEKDAYS,
            end_date=date(2026, 1, 14),
        )
        created = generate_occurrences(template)
        self.assertEqual(len(created), 10)


class RegenerateTests(OccurrenceGenerationTests):
    def make_member(self):
        return Person.objects.create(
            club=self.club,
            first_name="Kid",
            last_name="Small",
            personnummer=complete_pnr("160115123"),
            gender=Person.Gender.MALE,
            street_address="Gatan 1",
            postal_code="11122",
            city="Stockholm",
        )

    def test_regenerate_moves_future_occurrences(self):
        from attendance.models import AttendanceRecord

        template = self.make_template()
        generate_occurrences(template)
        today = date(2026, 1, 10)
        member = self.make_member()

        attended = Activity.objects.get(template=template, date=date(2026, 1, 26))
        AttendanceRecord.objects.create(activity=attended, person=member)

        manual = Activity.objects.get(template=template, date=date(2026, 2, 2))
        manual.is_manually_edited = True
        manual.save()

        template.weekday = Weekday.WEDNESDAY
        template.save()
        deleted_count, created_count = regenerate_occurrences(template, today=today)

        dates = set(
            Activity.objects.filter(template=template).values_list("date", flat=True)
        )
        self.assertIn(date(2026, 1, 5), dates)
        self.assertNotIn(date(2026, 1, 12), dates)
        self.assertNotIn(date(2026, 3, 30), dates)
        self.assertIn(date(2026, 1, 26), dates)
        self.assertIn(date(2026, 2, 2), dates)
        wednesdays = {d for d in dates if d.weekday() == 2}
        self.assertIn(date(2026, 1, 7), wednesdays)
        self.assertIn(date(2026, 3, 25), wednesdays)
        self.assertEqual(deleted_count, 10)
        self.assertEqual(created_count, 12)

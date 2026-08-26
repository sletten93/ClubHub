from datetime import date, time

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from attendance.models import AttendanceRecord
from clubs.models import Club
from groups.models import Group, GroupMembership
from people.models import Person, StaffProfile
from people.tests import complete_pnr
from scheduling.models import Activity, ActivityType, Season


class AttendanceTestBase(TestCase):
    def setUp(self):
        self.club = Club.objects.create(name="Att BK", slug="attbk")
        self.season = Season.objects.create(
            club=self.club,
            name="Vår 2026",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
        )
        self.group = Group.objects.create(club=self.club, name="Juniorer")
        self.member = self._make_person("Kid", "Small", "160115123", Person.Gender.MALE)
        self.trainer = self._make_person("Erik", "Coach", "830505123", Person.Gender.MALE)
        self.activity = Activity.objects.create(
            club=self.club,
            season=self.season,
            group=self.group,
            title="Träning",
            activity_type=ActivityType.TRAINING,
            date=date(2026, 2, 2),
            start_time=time(17, 0),
            end_time=time(18, 30),
        )
        GroupMembership.objects.create(group=self.group, person=self.member)
        GroupMembership.objects.create(
            group=self.group,
            person=self.trainer,
            role=GroupMembership.Role.TRAINER,
        )
        self.trainer_user = User.objects.create_user(username="trainer", password="pw12345!")
        StaffProfile.objects.create(person=self.trainer)
        self.trainer.user = self.trainer_user
        self.trainer.save()

    def _make_person(self, first_name, last_name, nine_digits, gender):
        return Person.objects.create(
            club=self.club,
            first_name=first_name,
            last_name=last_name,
            personnummer=complete_pnr(nine_digits),
            gender=gender,
            street_address="Gatan 1",
            postal_code="11122",
            city="Stockholm",
        )


class TakeAttendanceViewTests(AttendanceTestBase):
    def test_requires_login(self):
        url = reverse("attendance:take", kwargs={"pk": self.activity.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    def test_forbidden_without_staff_profile(self):
        outsider = User.objects.create_user(username="out", password="pw12345!")
        self.client.force_login(outsider)
        url = reverse("attendance:take", kwargs={"pk": self.activity.pk})
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_trainer_sees_roster(self):
        self.client.force_login(self.trainer_user)
        url = reverse("attendance:take", kwargs={"pk": self.activity.pk})
        response = self.client.get(url)
        self.assertContains(response, "Small, Kid")


class RecordUpdateTests(AttendanceTestBase):
    def test_trainer_can_record_status(self):
        self.client.force_login(self.trainer_user)
        url = reverse(
            "attendance:record",
            kwargs={"pk": self.activity.pk, "person_pk": self.member.pk},
        )
        response = self.client.post(url, {"status": "late"})
        self.assertEqual(response.status_code, 200)
        record = AttendanceRecord.objects.get(activity=self.activity, person=self.member)
        self.assertEqual(record.status, AttendanceRecord.Status.LATE)
        self.assertEqual(record.registered_by, self.trainer)

    def test_invalid_status_rejected(self):
        self.client.force_login(self.trainer_user)
        url = reverse(
            "attendance:record",
            kwargs={"pk": self.activity.pk, "person_pk": self.member.pk},
        )
        self.assertEqual(self.client.post(url, {"status": "nope"}).status_code, 400)

    def test_trainer_of_other_group_forbidden(self):
        stranger = self._make_person("Siv", "Remote", "800101123", Person.Gender.FEMALE)
        stranger_user = User.objects.create_user(username="remote", password="pw12345!")
        StaffProfile.objects.create(person=stranger)
        stranger.user = stranger_user
        stranger.save()
        other_group = Group.objects.create(club=self.club, name="Seniorer")
        GroupMembership.objects.create(
            group=other_group, person=stranger, role=GroupMembership.Role.TRAINER
        )
        self.client.force_login(stranger_user)
        url = reverse(
            "attendance:record",
            kwargs={"pk": self.activity.pk, "person_pk": self.member.pk},
        )
        response = self.client.post(url, {"status": "present"})
        self.assertEqual(response.status_code, 404)


class BulkPresentTests(AttendanceTestBase):
    def test_marks_all_roster_present(self):
        extra_member = self._make_person("Anna", "Second", "900303123", Person.Gender.FEMALE)
        GroupMembership.objects.create(group=self.group, person=extra_member)
        self.client.force_login(self.trainer_user)
        url = reverse("attendance:bulk_present", kwargs={"pk": self.activity.pk})
        response = self.client.post(url, follow=True)
        self.assertContains(response, "2 / 2")
        records = AttendanceRecord.objects.filter(activity=self.activity)
        self.assertEqual(records.count(), 2)
        self.assertTrue(all(r.status == AttendanceRecord.Status.PRESENT for r in records))

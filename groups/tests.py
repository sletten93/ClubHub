from django.core.exceptions import ValidationError
from django.test import TestCase

from clubs.models import Club
from people.models import Person, StaffProfile
from people.tests import complete_pnr

from .models import Group, GroupMembership


class GroupMembershipTests(TestCase):
    def setUp(self):
        self.club = Club.objects.create(name="Test BK", slug="testbk")
        self.group = Group.objects.create(club=self.club, name="Juniorer")
        self.person = Person.objects.create(
            club=self.club,
            first_name="Anna",
            last_name="Andersson",
            personnummer=complete_pnr("870512123"),
            gender=Person.Gender.FEMALE,
            street_address="Gatan 1",
            postal_code="11122",
            city="Stockholm",
        )

    def test_member_needs_no_staff_profile(self):
        GroupMembership(group=self.group, person=self.person).full_clean()

    def test_trainer_requires_staff_profile(self):
        membership = GroupMembership(
            group=self.group, person=self.person, role=GroupMembership.Role.TRAINER
        )
        with self.assertRaises(ValidationError):
            membership.full_clean()
        StaffProfile.objects.create(person=self.person)
        membership.full_clean()

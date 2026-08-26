from datetime import date

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from clubs.models import Club
from groups.models import Group, GroupMembership

from . import services
from .models import GuardianRelation, Membership, Person, StaffProfile
from .personnummer import _luhn, birth_date_from_personnummer


def complete_pnr(nine_digits):
    for digit in range(10):
        candidate = f"{nine_digits}{digit}"
        if _luhn(candidate):
            return candidate
    raise AssertionError("No valid checksum digit found")


class PersonnummerTests(TestCase):
    def setUp(self):
        self.club = Club.objects.create(name="Test BK", slug="testbk")

    def make_person(self, personnummer, **kwargs):
        defaults = dict(
            club=self.club,
            first_name="Anna",
            last_name="Andersson",
            gender=Person.Gender.FEMALE,
            street_address="Gatan 1",
            postal_code="11122",
            city="Stockholm",
        )
        defaults.update(kwargs)
        return Person.objects.create(personnummer=personnummer, **defaults)

    def test_save_normalizes_to_12_digits(self):
        pnr10 = complete_pnr("870512123")
        person = self.make_person(f"{pnr10[:6]}-{pnr10[6:]}")
        self.assertEqual(person.personnummer, "19870512" + pnr10[6:])
        self.assertEqual(person.birth_date, date(1987, 5, 12))

    def test_invalid_checksum_rejected(self):
        with self.assertRaises(ValidationError):
            self.make_person(complete_pnr("870512123")[:-1] + ("0" if complete_pnr("870512123")[-1] != "0" else "1"))

    def test_samordningsnummer_accepted(self):
        pnr10 = complete_pnr("870562123")
        person = self.make_person(pnr10)
        self.assertEqual(person.personnummer, "19870562" + pnr10[6:])
        self.assertEqual(person.birth_date, date(1987, 5, 2))

    def test_is_minor(self):
        adult = self.make_person(complete_pnr("870512123"), last_name="Adult")
        child = self.make_person(complete_pnr("160115123"), last_name="Child")
        self.assertFalse(adult.is_minor)
        self.assertTrue(child.is_minor)


class MembershipGuardianRuleTests(TestCase):
    def setUp(self):
        self.club = Club.objects.create(name="Test BK", slug="testbk")

    def make_person(self, personnummer, first_name, last_name):
        return Person.objects.create(
            club=self.club,
            first_name=first_name,
            last_name=last_name,
            personnummer=personnummer,
            gender=Person.Gender.FEMALE,
            street_address="Gatan 1",
            postal_code="11122",
            city="Stockholm",
        )

    def test_minor_requires_guardian(self):
        adult = self.make_person(complete_pnr("800101123"), "Guard", "Ian")
        child = self.make_person(complete_pnr("160115123"), "Kid", "Small")
        membership = Membership(person=child, start_date=date(2026, 1, 1))
        with self.assertRaises(ValidationError):
            membership.full_clean()
        GuardianRelation.objects.create(guardian=adult, child=child)
        membership.full_clean()

    def test_adult_needs_no_guardian(self):
        adult = self.make_person(complete_pnr("800101123"), "Big", "Person")
        Membership(person=adult, start_date=date(2026, 1, 1)).full_clean()


class AccessServiceTests(TestCase):
    def setUp(self):
        self.club = Club.objects.create(name="Test BK", slug="testbk")

    def make_user_person(self, username, is_admin=False, nine_digits="850101123"):
        user = User.objects.create_user(username=username, password="pw12345!")
        person = Person.objects.create(
            club=self.club,
            first_name="A",
            last_name=username.title(),
            personnummer=complete_pnr(nine_digits),
            gender=Person.Gender.FEMALE,
            street_address="Gatan 1",
            postal_code="11122",
            city="Stockholm",
            user=user,
        )
        StaffProfile.objects.create(person=person, is_admin=is_admin)
        return user, person

    def test_plain_user_has_no_person(self):
        user = User.objects.create_user(username="plain", password="pw12345!")
        self.assertIsNone(services.get_person(user))
        self.assertFalse(services.has_staff_profile(user))
        self.assertFalse(services.is_admin(user))

    def test_is_admin_flag_respected(self):
        admin_user, _ = self.make_user_person("boss", is_admin=True, nine_digits="820202123")
        trainer_user, _ = self.make_user_person("coach", is_admin=False, nine_digits="870512123")
        self.assertTrue(services.is_admin(admin_user))
        self.assertFalse(services.is_admin(trainer_user))
        self.assertTrue(services.has_staff_profile(trainer_user))

    def test_visible_groups_scoping(self):
        trainer_user, trainer_person = self.make_user_person("coach", nine_digits="870512123")
        admin_user, admin_person = self.make_user_person("boss", is_admin=True, nine_digits="820202123")
        own = Group.objects.create(club=self.club, name="Egna")
        other = Group.objects.create(club=self.club, name="Främmande")
        GroupMembership.objects.create(
            group=own, person=trainer_person, role=GroupMembership.Role.TRAINER
        )
        self.assertEqual(list(services.visible_groups(trainer_user)), [own])
        self.assertEqual(set(services.visible_groups(admin_user)), {own, other})
        self.assertTrue(services.can_manage_group(trainer_user, own))
        self.assertFalse(services.can_manage_group(trainer_user, other))


class AuthFlowTests(TestCase):
    def setUp(self):
        self.club = Club.objects.create(name="Login BK", slug="loginbk")
        self.user = User.objects.create_user(username="anna", password="starkpass1")
        person = Person.objects.create(
            club=self.club,
            first_name="Anna",
            last_name="Ekström",
            personnummer=complete_pnr("850101123"),
            gender=Person.Gender.FEMALE,
            street_address="Gatan 1",
            postal_code="11122",
            city="Stockholm",
            user=self.user,
        )
        StaffProfile.objects.create(person=person)

    def test_login_page_reachable(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)

    def test_login_redirects_to_dashboard(self):
        response = self.client.post(
            reverse("login"), {"username": "anna", "password": "starkpass1"}
        )
        self.assertRedirects(response, reverse("clubs:home"))
        page = self.client.get(reverse("clubs:home"))
        self.assertContains(page, "Hej Anna")

    def test_home_forbidden_without_profile(self):
        outsider = User.objects.create_user(username="out", password="starkpass1")
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(reverse("clubs:home")).status_code, 403)

    def test_home_requires_login(self):
        response = self.client.get(reverse("clubs:home"))
        self.assertEqual(response.status_code, 302)

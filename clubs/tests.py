import base64
import shutil
import tempfile
from datetime import date

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from clubs.utils import build_theme, readable_text, shade
from groups.models import Group, GroupMembership
from people.models import Person, StaffProfile
from people.tests import complete_pnr
from scheduling.models import Season

PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


class ColorUtilTests(TestCase):
    def test_shade_darkens_and_lightens(self):
        self.assertEqual(shade("#ff0000", -0.5), "#800000")
        self.assertEqual(shade("#000000", 1.0), "#ffffff")
        self.assertEqual(shade("#0d6efd", 0.0), "#0d6efd")

    def test_readable_text_contrast(self):
        self.assertEqual(readable_text("#ffffff"), "#212529")
        self.assertEqual(readable_text("#000000"), "#ffffff")

    def test_build_theme(self):
        class Stub:
            primary_color = "#FF0000"
            secondary_color = "#0000ff"

        theme = build_theme(Stub())
        self.assertEqual(theme["primary"], "#ff0000")
        self.assertEqual(theme["primary_rgb"], "255,0,0")
        self.assertEqual(theme["on_primary"], "#ffffff")


def make_staff_user(username, is_admin=False, club=None, nine_digits="850101123"):
    from clubs.models import Club

    if club is None:
        club = Club.objects.create(name="Style BK", slug="stylebk")
    user = User.objects.create_user(username=username, password="pw12345!")
    person = Person.objects.create(
        club=club,
        first_name="A",
        last_name=username.title(),
        personnummer=complete_pnr(nine_digits),
        gender=Person.Gender.FEMALE,
        street_address="Gatan 1",
        postal_code="11122",
        city="Stockholm",
    )
    person.user = user
    person.save()
    StaffProfile.objects.create(person=person, is_admin=is_admin)
    return person, user


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ClubSettingsTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._temp_media(), ignore_errors=True)
        super().tearDownClass()

    @classmethod
    def _temp_media(cls):
        import django.conf

        return str(django.conf.settings.MEDIA_ROOT)

    def setUp(self):
        from clubs.models import Club

        self.club = Club.objects.create(name="Style BK", slug="stylebk")
        self.admin_person, self.admin_user = make_staff_user(
            "boss", is_admin=True, club=self.club
        )
        _, self.trainer_user = make_staff_user(
            "coach", is_admin=False, club=self.club, nine_digits="870512123"
        )
        Season.objects.create(
            club=self.club,
            name="Vår",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
        )

    def test_settings_requires_admin(self):
        url = reverse("clubs:settings")
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.trainer_user)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_settings_renders_for_admin(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("clubs:settings"))
        self.assertContains(response, 'type="color"')
        self.assertContains(response, "Logotyp")

    def test_update_colors(self):
        self.client.force_login(self.admin_user)
        response = self.client.post(
            reverse("clubs:settings"),
            {
                "name": "Style BK Boxning",
                "organisation_number": "",
                "email": "",
                "phone": "",
                "street_address": "",
                "postal_code": "",
                "city": "",
                "primary_color": "#D92B2B",
                "secondary_color": "#1f1f1f",
            },
            follow=True,
        )
        self.assertContains(response, "sparats")
        self.club.refresh_from_db()
        self.assertEqual(self.club.primary_color, "#d92b2b")
        self.assertEqual(self.club.secondary_color, "#1f1f1f")
        self.assertEqual(self.club.name, "Style BK Boxning")

    def test_invalid_color_rejected(self):
        self.client.force_login(self.admin_user)
        self.client.post(
            reverse("clubs:settings"),
            {
                "name": "Style BK",
                "organisation_number": "",
                "email": "",
                "phone": "",
                "street_address": "",
                "postal_code": "",
                "city": "",
                "primary_color": "red",
                "secondary_color": "#1f1f1f",
            },
        )
        self.club.refresh_from_db()
        self.assertEqual(self.club.primary_color, "#0d6efd")

    def test_logo_upload_shows_in_navbar_and_dashboard(self):
        upload = SimpleUploadedFile("logo.png", PNG_1PX, content_type="image/png")
        self.client.force_login(self.admin_user)
        self.client.post(
            reverse("clubs:settings"),
            {
                "name": "Style BK",
                "organisation_number": "",
                "email": "",
                "phone": "",
                "street_address": "",
                "postal_code": "",
                "city": "",
                "primary_color": "#0d6efd",
                "secondary_color": "#212529",
                "logo": upload,
            },
        )
        self.club.refresh_from_db()
        self.assertTrue(self.club.logo)
        response = self.client.get(reverse("clubs:home"))
        self.assertContains(response, self.club.logo.url)

    def _upload_logo(self):
        upload = SimpleUploadedFile("logo.png", PNG_1PX, content_type="image/png")
        self.client.force_login(self.admin_user)
        self.client.post(
            reverse("clubs:settings"),
            {
                "name": "Style BK",
                "organisation_number": "",
                "email": "",
                "phone": "",
                "street_address": "",
                "postal_code": "",
                "city": "",
                "primary_color": "#0d6efd",
                "secondary_color": "#212529",
                "logo": upload,
            },
        )
        self.club.refresh_from_db()

    def test_remove_image_clears_logo_for_admin(self):
        self._upload_logo()
        self.assertTrue(self.club.logo)
        response = self.client.post(
            reverse("clubs:remove_image"), {"field": "logo"}
        )
        self.assertEqual(response.status_code, 200)
        self.club.refresh_from_db()
        self.assertFalse(self.club.logo)

    def test_remove_image_rejects_trainer_and_unknown_field(self):
        self._upload_logo()
        self.client.force_login(self.trainer_user)
        response = self.client.post(
            reverse("clubs:remove_image"), {"field": "logo"}
        )
        self.assertEqual(response.status_code, 403)

        self.client.force_login(self.admin_user)
        response = self.client.post(
            reverse("clubs:remove_image"), {"field": "name"}
        )
        self.assertEqual(response.status_code, 400)
        self.club.refresh_from_db()
        self.assertTrue(self.club.logo)

    def test_remove_image_requires_login(self):
        response = self.client.post(
            reverse("clubs:remove_image"), {"field": "logo"}
        )
        self.assertEqual(response.status_code, 302)

    def test_theme_css_applied_on_home(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("clubs:home"))
        self.assertContains(response, ".btn-primary")
        self.assertContains(response, "#0d6efd")


@override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"])
class NotFoundPageTests(TestCase):
    def test_custom_404_page(self):
        response = self.client.get("/this-page-does-not-exist/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "404", status_code=404)


class UserSettingsTests(TestCase):
    def setUp(self):
        from clubs.models import Club

        self.club = Club.objects.create(name="Style BK", slug="stylebk")
        self.admin_person, self.admin_user = make_staff_user(
            "boss", is_admin=True, club=self.club
        )

    def test_settings_requires_login(self):
        response = self.client.get(reverse("clubs:user_settings"))
        self.assertEqual(response.status_code, 302)

    def test_settings_page_renders(self):
        self.client.force_login(self.admin_user)
        self.admin_user.first_name = "Anna"
        self.admin_user.save()
        response = self.client.get(reverse("clubs:user_settings"))
        self.assertContains(response, 'action="/settings/password/"')
        self.assertContains(response, 'type="password"')
        self.assertContains(response, "Språk")
        self.assertContains(response, 'placeholder="Anna"')
        self.assertContains(response, "Nuvarande lösenord")
        self.assertContains(response, "Minst 8 tecken")

    def test_update_profile_fields_and_language(self):
        self.client.force_login(self.admin_user)
        response = self.client.post(
            reverse("clubs:user_settings"),
            {
                "first_name": "Anna",
                "last_name": "Andersson",
                "email": "anna@example.com",
            },
            follow=True,
        )
        # Language lives in its own form on the page.
        response = self.client.post(
            reverse("clubs:user_settings"),
            {"form": "language", "language": "en-GB"},
            follow=True,
        )
        self.admin_user.refresh_from_db()
        self.admin_person.refresh_from_db()
        self.assertEqual(self.admin_user.email, "anna@example.com")
        self.assertEqual(self.admin_user.first_name, "Anna")
        self.assertEqual(self.admin_person.email, "anna@example.com")
        self.assertEqual(self.admin_user.profile.language, "en-GB")
        # The interface renders in the user's chosen language afterwards.
        self.assertContains(response, "Account")
        self.assertContains(response, "Language")

    def test_blank_profile_fields_keep_current_values(self):
        self.client.force_login(self.admin_user)
        self.admin_user.first_name = "Anna"
        self.admin_user.email = "anna@example.com"
        self.admin_user.save()
        self.client.post(reverse("clubs:user_settings"), {"email": ""})
        self.admin_user.refresh_from_db()
        self.assertEqual(self.admin_user.first_name, "Anna")
        self.assertEqual(self.admin_user.email, "anna@example.com")

    def test_invalid_language_falls_back_to_default(self):
        self.client.force_login(self.admin_user)
        response = self.client.post(
            reverse("clubs:user_settings"),
            {"form": "language", "language": "not-a-language"},
            follow=True,
        )
        # Unknown codes are ignored: nothing is saved, no flash message.
        self.admin_user.refresh_from_db()
        self.assertEqual(self.admin_user.profile.language, "")
        self.assertNotContains(response, "sparats")

    def test_password_change_and_old_url_redirect(self):
        response = self.client.get("/accounts/password_change/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.endswith("/settings/"))

        self.client.force_login(self.admin_user)
        response = self.client.post(
            reverse("clubs:user_password"),
            {
                "old_password": "pw12345!",
                "new_password1": "newpass99!",
                "new_password2": "newpass99!",
            },
            follow=True,
        )
        self.assertContains(response, "ändrats")
        self.admin_user.refresh_from_db()
        self.assertTrue(self.admin_user.check_password("newpass99!"))

    def test_favicon_uses_club_logo(self):
        self.club.logo = SimpleUploadedFile("logo.png", PNG_1PX, content_type="image/png")
        self.club.save()
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("clubs:home"))
        self.assertContains(response, 'rel="icon"')
        self.assertContains(response, self.club.logo.url)

from datetime import date

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models

from clubs.models import Club

from .personnummer import birth_date_from_personnummer, normalize_personnummer


def validate_personnummer(value):
    normalize_personnummer(value)


class Person(models.Model):
    class Gender(models.TextChoices):
        MALE = "male", "Male"
        FEMALE = "female", "Female"
        NON_BINARY = "non_binary", "Non-binary"

    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name="people")
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    personnummer = models.CharField(
        max_length=12, validators=[validate_personnummer], help_text="Stored as YYYYMMDDXXXX."
    )
    gender = models.CharField(max_length=20, choices=Gender.choices)
    street_address = models.CharField(max_length=200)
    postal_code = models.CharField(max_length=10)
    city = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    phone_mobile = models.CharField(max_length=30, blank=True)
    notes = models.TextField(blank=True)
    allergy = models.TextField(blank=True)
    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="person",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["last_name", "first_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["club", "personnummer"], name="uniq_person_pnr_per_club"
            )
        ]

    def save(self, *args, **kwargs):
        self.personnummer = normalize_personnummer(self.personnummer)
        super().save(*args, **kwargs)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def birth_date(self):
        return birth_date_from_personnummer(self.personnummer)

    @property
    def is_minor(self):
        born = self.birth_date
        if born is None:
            return False
        today = date.today()
        return born > today.replace(year=today.year - 18)

    @property
    def is_member(self):
        return hasattr(self, "membership")

    @property
    def is_staff_member(self):
        return hasattr(self, "staff_profile")

    def __str__(self):
        return self.full_name


class AdminGroup(models.Model):
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name="admin_groups")
    name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["club", "name"], name="uniq_admingroup_per_club")
        ]

    def __str__(self):
        return f"{self.name} ({self.club.name})"


class StaffProfile(models.Model):
    person = models.OneToOneField(Person, on_delete=models.CASCADE, related_name="staff_profile")
    is_admin = models.BooleanField(default=False)
    admin_groups = models.ManyToManyField(AdminGroup, blank=True, related_name="staff_members")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        role = "Admin" if self.is_admin else "Trainer"
        return f"{self.person.full_name} ({role})"


class Membership(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Aktiv"
        INACTIVE = "inactive", "Inaktiv"
        PAUSED = "paused", "Pausad"

    class PaymentStatus(models.TextChoices):
        PAID = "paid", "Betald"
        PARTLY_PAID = "partly_paid", "Delvis betald"
        UNPAID = "unpaid", "Obetald"

    person = models.OneToOneField(Person, on_delete=models.CASCADE, related_name="membership")
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE
    )
    payment_status = models.CharField(
        max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID
    )
    start_date = models.DateField()
    disability = models.CharField(max_length=500, blank=True)
    photo_consent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        if self.person_id and self.person.is_minor and not self.person.guarded_by.exists():
            raise ValidationError(
                {"person": "Members under 18 must have at least one registered guardian."}
            )

    def __str__(self):
        return f"{self.person.full_name} ({self.get_status_display()})"


class GuardianRelation(models.Model):
    guardian = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="guardian_of")
    child = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="guarded_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["child__last_name", "child__first_name"]
        constraints = [
            models.UniqueConstraint(fields=["guardian", "child"], name="uniq_guardian_child")
        ]

    def clean(self):
        if self.guardian_id == self.child_id:
            raise ValidationError("A person cannot be their own guardian.")

    def __str__(self):
        return f"{self.guardian.full_name} guardian of {self.child.full_name}"

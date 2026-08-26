from django.core.exceptions import ValidationError
from django.db import models

from clubs.models import Club
from people.models import Person


class Group(models.Model):
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name="groups")
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    members = models.ManyToManyField(
        Person, through="GroupMembership", related_name="groups", blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["club", "name"], name="uniq_group_per_club")
        ]

    def __str__(self):
        return self.name


class GroupMembership(models.Model):
    class Role(models.TextChoices):
        MEMBER = "member", "Member"
        TRAINER = "trainer", "Trainer"

    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="memberships")
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="group_memberships")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)
    joined_on = models.DateField(auto_now_add=True)
    left_on = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["group__name", "person__last_name"]
        constraints = [
            models.UniqueConstraint(fields=["group", "person"], name="uniq_person_per_group")
        ]

    def clean(self):
        if (
            self.role == self.Role.TRAINER
            and self.person_id
            and not self.person.is_staff_member
        ):
            raise ValidationError(
                {"person": "Trainers must have a staff profile."}
            )

    def __str__(self):
        return f"{self.person.full_name} ({self.get_role_display()} in {self.group.name})"

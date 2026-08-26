from django.db import models

from clubs.models import Club
from people.models import Person
from scheduling.models import Activity


class AttendanceRecord(models.Model):
    class Status(models.TextChoices):
        PRESENT = "present", "Närvarande"
        LATE = "late", "Sen"
        ABSENT = "absent", "Frånvarande"
        EXCUSED = "excused", "Godkänd frånvaro"

    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name="attendance_records")
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE, related_name="attendance_records")
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="attendance_records")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PRESENT)
    registered_by = models.ForeignKey(
        Person,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_registrations",
    )
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if self.activity_id and not self.club_id:
            self.club = self.activity.club
        super().save(*args, **kwargs)

    class Meta:
        ordering = ["activity__date", "person__last_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["activity", "person"], name="uniq_attendance_per_activity_person"
            )
        ]

    def __str__(self):
        return f"{self.person.full_name} - {self.get_status_display()} at {self.activity}"

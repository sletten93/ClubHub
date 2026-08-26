from django.db import models

from clubs.models import Club
from groups.models import Group
from people.models import Person


class Notification(models.Model):
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name="notifications")
    subject = models.CharField(max_length=200)
    body = models.TextField()
    all_members = models.BooleanField(default=False)
    groups = models.ManyToManyField(Group, blank=True, related_name="notifications")
    created_by = models.ForeignKey(
        Person,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.subject


class NotificationRecipient(models.Model):
    notification = models.ForeignKey(
        Notification, on_delete=models.CASCADE, related_name="recipients"
    )
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="notifications")
    sent_at = models.DateTimeField(null=True, blank=True)
    error = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["person__last_name", "person__first_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["notification", "person"], name="uniq_recipient_per_notification"
            )
        ]

    def __str__(self):
        return f"{self.person.full_name} - {self.notification.subject}"

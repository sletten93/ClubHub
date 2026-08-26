from django.core.exceptions import ValidationError
from django.db import models

from clubs.models import Club
from groups.models import Group


class ActivityType(models.TextChoices):
    TRAINING = "training", "Träningspass"
    COMPETITION = "competition", "Tävling"
    MEETING = "meeting", "Möte"


class Weekday(models.IntegerChoices):
    MONDAY = 0, "Måndag"
    TUESDAY = 1, "Tisdag"
    WEDNESDAY = 2, "Onsdag"
    THURSDAY = 3, "Torsdag"
    FRIDAY = 4, "Fredag"
    SATURDAY = 5, "Lördag"
    SUNDAY = 6, "Söndag"


class Season(models.Model):
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name="seasons")
    name = models.CharField(max_length=200)
    start_date = models.DateField()
    end_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_date"]
        constraints = [
            models.UniqueConstraint(fields=["club", "name"], name="uniq_season_per_club")
        ]

    def clean(self):
        if self.start_date and self.end_date and self.end_date <= self.start_date:
            raise ValidationError({"end_date": "End date must be after start date."})

    def __str__(self):
        return self.name


class ActivityTemplate(models.Model):
    class Recurrence(models.TextChoices):
        NONE = "none", "Aldrig"
        DAILY = "daily", "Varje dag"
        WEEKDAYS = "weekdays", "Vardagar"
        WEEKLY = "weekly", "Varje vecka"
        MONTHLY = "monthly", "Varje månad"

    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name="activity_templates")
    season = models.ForeignKey(Season, on_delete=models.PROTECT, related_name="activity_templates")
    group = models.ForeignKey(Group, on_delete=models.PROTECT, related_name="activity_templates")
    title = models.CharField(max_length=200)
    activity_type = models.CharField(max_length=20, choices=ActivityType.choices)
    recurrence = models.CharField(
        max_length=20, choices=Recurrence.choices, default=Recurrence.WEEKLY
    )
    weekday = models.IntegerField(choices=Weekday.choices, null=True, blank=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    start_date = models.DateField(null=True, blank=True, help_text="Defaults to season start.")
    end_date = models.DateField(null=True, blank=True, help_text="Defaults to season end.")
    location = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start_time"]

    @property
    def effective_start_date(self):
        return self.start_date or self.season.start_date

    @property
    def effective_end_date(self):
        if self.end_date and self.end_date < self.season.end_date:
            return self.end_date
        return self.season.end_date

    def clean(self):
        errors = {}
        if self.recurrence == self.Recurrence.WEEKLY and self.weekday is None:
            errors["weekday"] = "Weekday is required for weekly recurrence."
        if (
            self.start_time
            and self.end_time
            and self.end_time <= self.start_time
        ):
            errors["end_time"] = "End time must be after start time."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.title} ({self.get_recurrence_display()}, {self.group.name})"


class Activity(models.Model):
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name="activities")
    season = models.ForeignKey(Season, on_delete=models.PROTECT, related_name="activities")
    group = models.ForeignKey(Group, on_delete=models.PROTECT, related_name="activities")
    template = models.ForeignKey(
        ActivityTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="occurrences",
    )
    title = models.CharField(max_length=200)
    activity_type = models.CharField(max_length=20, choices=ActivityType.choices)
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    location = models.CharField(max_length=200, blank=True)
    is_cancelled = models.BooleanField(default=False)
    is_manually_edited = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["date", "start_time"]
        indexes = [models.Index(fields=["club", "date"])]
        constraints = [
            models.UniqueConstraint(
                fields=["template", "date"],
                condition=models.Q(template__isnull=False),
                name="uniq_occurrence_per_template_and_date",
            )
        ]

    def clean(self):
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValidationError({"end_time": "End time must be after start time."})

    def __str__(self):
        return f"{self.title} {self.date} {self.start_time}"

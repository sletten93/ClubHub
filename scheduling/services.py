import datetime

from dateutil.rrule import DAILY, FR, MO, MONTHLY, SA, SU, TH, TU, WE, WEEKLY, rrule
from django.utils import timezone

from attendance.models import AttendanceRecord

from .models import Activity, ActivityTemplate

_WEEKDAYS = {0: MO, 1: TU, 2: WE, 3: TH, 4: FR, 5: SA, 6: SU}
_WEEKDAY_SET = (MO, TU, WE, TH, FR)


def _occurrence_dates(template):
    recurrence = template.recurrence
    start = template.effective_start_date
    end = template.effective_end_date
    if recurrence == ActivityTemplate.Recurrence.NONE:
        return [start]
    dtstart = datetime.datetime.combine(start, datetime.time.min)
    if recurrence == ActivityTemplate.Recurrence.DAILY:
        rule = rrule(DAILY, dtstart=dtstart, until=end)
    elif recurrence == ActivityTemplate.Recurrence.WEEKDAYS:
        rule = rrule(DAILY, dtstart=dtstart, until=end, byweekday=_WEEKDAY_SET)
    elif recurrence == ActivityTemplate.Recurrence.WEEKLY:
        rule = rrule(
            WEEKLY, dtstart=dtstart, until=end, byweekday=_WEEKDAYS[template.weekday]
        )
    elif recurrence == ActivityTemplate.Recurrence.MONTHLY:
        rule = rrule(MONTHLY, dtstart=dtstart, until=end)
    else:
        return []
    return [result.date() for result in rule]


def generate_occurrences(template):
    """Create every missing occurrence for a template in bulk.

    Idempotent like the previous get_or_create loop: dates that already have
    an Activity (attendance-protected or manually edited ones included) are
    skipped untouched. The (template, date) unique constraint in
    scheduling.models.Activity backs this up under races.
    """
    occurrence_dates = _occurrence_dates(template)
    if not occurrence_dates:
        return []
    existing_dates = set(
        Activity.objects.filter(template=template, date__in=occurrence_dates).values_list(
            "date", flat=True
        )
    )
    missing = [
        Activity(
            club=template.club,
            season=template.season,
            group=template.group,
            template=template,
            title=template.title,
            activity_type=template.activity_type,
            date=occurrence_date,
            start_time=template.start_time,
            end_time=template.end_time,
            location=template.location,
        )
        for occurrence_date in occurrence_dates
        if occurrence_date not in existing_dates
    ]
    return Activity.objects.bulk_create(missing)


def regenerate_occurrences(template, today=None):
    today = today or timezone.localdate()
    protected_ids = set(
        AttendanceRecord.objects.filter(activity__template=template).values_list(
            "activity_id", flat=True
        )
    )
    stale = (
        Activity.objects.filter(template=template, date__gte=today)
        .exclude(is_manually_edited=True)
        .exclude(id__in=protected_ids)
    )
    deleted_count = stale.count()
    stale.delete()
    created = generate_occurrences(template)
    return deleted_count, len(created)

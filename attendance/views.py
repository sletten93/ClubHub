from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import DetailView

from clubs.translations import translate
from groups.models import GroupMembership
from people.mixins import StaffRequiredMixin
from people import services

from .models import AttendanceRecord

STATUS_OPTIONS = [
    {"value": choice.value, "label": choice.label, "color": color}
    for choice, color in (
        (AttendanceRecord.Status.PRESENT, "success"),
        (AttendanceRecord.Status.LATE, "warning"),
        (AttendanceRecord.Status.ABSENT, "danger"),
        (AttendanceRecord.Status.EXCUSED, "secondary"),
    )
]


def _visible_activity(request, pk):
    return get_object_or_404(
        services.visible_activities(request.user).select_related("group"), pk=pk
    )


def _check_can_manage(request, activity):
    if not services.can_manage_group(request.user, activity.group):
        raise PermissionDenied


def _roster(activity):
    return (
        GroupMembership.objects.filter(
            group=activity.group,
            role=GroupMembership.Role.MEMBER,
            left_on__isnull=True,
        )
        .select_related("person")
        .order_by("person__last_name", "person__first_name")
    )


def _row_context(activity, person, record):
    return {
        "activity": activity,
        "person": person,
        "current": record.status if record else "",
        "statuses": STATUS_OPTIONS,
    }


class TakeAttendanceView(StaffRequiredMixin, DetailView):
    template_name = "attendance/activity_attendance.html"
    context_object_name = "activity"

    def get_queryset(self):
        return services.visible_activities(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        activity = self.object
        records = {
            record.person_id: record
            for record in AttendanceRecord.objects.filter(activity=activity)
        }
        context["roster_rows"] = [
            {
                "person": membership.person,
                "record": records.get(membership.person_id),
            }
            for membership in _roster(activity)
        ]
        context["statuses"] = STATUS_OPTIONS
        present_count = sum(
            1
            for row in context["roster_rows"]
            if row["record"] and row["record"].status in (
                AttendanceRecord.Status.PRESENT,
                AttendanceRecord.Status.LATE,
            )
        )
        context["present_count"] = present_count
        context["roster_count"] = len(context["roster_rows"])
        return context


@require_POST
def record_update(request, pk, person_pk):
    activity = _visible_activity(request, pk)
    _check_can_manage(request, activity)
    status = request.POST.get("status")
    if status not in AttendanceRecord.Status.values:
        return HttpResponseBadRequest("Invalid status")
    record, _ = AttendanceRecord.objects.update_or_create(
        activity=activity,
        person_id=person_pk,
        defaults={
            "status": status,
            "registered_by": services.get_person(request.user),
        },
    )
    return render(
        request,
        "attendance/_attendance_row.html",
        _row_context(activity, record.person, record),
    )


@require_POST
def bulk_present(request, pk):
    activity = _visible_activity(request, pk)
    _check_can_manage(request, activity)
    registered_by = services.get_person(request.user)
    with transaction.atomic():
        for membership in _roster(activity):
            AttendanceRecord.objects.update_or_create(
                activity=activity,
                person=membership.person,
                defaults={
                    "status": AttendanceRecord.Status.PRESENT,
                    "registered_by": registered_by,
                },
            )
    messages.success(request, translate("Alla markerades som närvarande.", "Närvaro"))
    return redirect(reverse("attendance:take", kwargs={"pk": activity.pk}))

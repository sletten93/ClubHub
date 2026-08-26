from datetime import timedelta

from django.utils import timezone
from rest_framework import generics
from rest_framework.exceptions import NotFound, ValidationError

from clubs.models import Club
from groups.models import Group
from scheduling.models import Activity, Season

from .serializers import ActivitySerializer, ClubSerializer, GroupSerializer, SeasonSerializer

MAX_RANGE_DAYS = 366


def _get_club(slug):
    club = Club.objects.filter(slug=slug).first()
    if club is None:
        raise NotFound("Club not found.")
    return club


def _parse_date(value):
    try:
        return timezone.datetime.fromisoformat(value).date()
    except (TypeError, ValueError):
        return None


class ClubListAPIView(generics.ListAPIView):
    queryset = Club.objects.all()
    serializer_class = ClubSerializer
    pagination_class = None


class ClubSeasonsAPIView(generics.ListAPIView):
    serializer_class = SeasonSerializer
    pagination_class = None

    def get_queryset(self):
        return (
            Season.objects.filter(club=_get_club(self.kwargs["slug"]))
            .order_by("-start_date")
        )


class ClubGroupsAPIView(generics.ListAPIView):
    serializer_class = GroupSerializer
    pagination_class = None

    def get_queryset(self):
        return Group.objects.filter(club=_get_club(self.kwargs["slug"])).order_by("name")


class ClubScheduleAPIView(generics.ListAPIView):
    serializer_class = ActivitySerializer
    pagination_class = None

    def get_queryset(self):
        club = _get_club(self.kwargs["slug"])
        today = timezone.localdate()
        start = _parse_date(self.request.query_params.get("from")) or today
        end = _parse_date(self.request.query_params.get("to")) or today + timedelta(days=30)
        if end < start:
            raise ValidationError("'to' must not be before 'from'.")
        if (end - start).days > MAX_RANGE_DAYS:
            raise ValidationError("Range must not exceed 366 days.")
        return (
            Activity.objects.filter(club=club, date__gte=start, date__lte=end)
            .select_related("group")
            .order_by("date", "start_time")
        )

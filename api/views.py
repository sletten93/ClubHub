from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from rest_framework import generics
from rest_framework.exceptions import NotFound, ValidationError

from clubs.models import Club
from groups.models import Group
from scheduling.models import Activity, Season

from .serializers import ActivitySerializer, ClubSerializer, GroupSerializer, SeasonSerializer

MAX_RANGE_DAYS = 366

# All endpoints are anonymous, shared, slow-moving data — safe to cache per
# URL (incl. query string) for a minute. Errors are raised, so they are never
# cached. In DEBUG the timeout is 0: cache_page still stamps responses with
# Cache-Control: max-age=0 (browsers refetch) and skips the store, so edits
# show up instantly while developing. Swap the default LocMem cache for
# Redis/Memcached when deploying multi-process.
API_CACHE_SECONDS = 0 if settings.DEBUG else 60


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


@method_decorator(cache_page(API_CACHE_SECONDS), name="dispatch")
class ClubListAPIView(generics.ListAPIView):
    queryset = Club.objects.all()
    serializer_class = ClubSerializer
    pagination_class = None


@method_decorator(cache_page(API_CACHE_SECONDS), name="dispatch")
class ClubSeasonsAPIView(generics.ListAPIView):
    serializer_class = SeasonSerializer
    pagination_class = None

    def get_queryset(self):
        return (
            Season.objects.filter(club=_get_club(self.kwargs["slug"]))
            .order_by("-start_date")
        )


@method_decorator(cache_page(API_CACHE_SECONDS), name="dispatch")
class ClubGroupsAPIView(generics.ListAPIView):
    serializer_class = GroupSerializer
    pagination_class = None

    def get_queryset(self):
        return Group.objects.filter(club=_get_club(self.kwargs["slug"])).order_by("name")


@method_decorator(cache_page(API_CACHE_SECONDS), name="dispatch")
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

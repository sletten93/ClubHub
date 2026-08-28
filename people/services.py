from groups.models import Group, GroupMembership
from scheduling.models import Activity

from .models import Person


def get_person(user):
    if not user.is_authenticated:
        return None
    # Cached on the user instance so the several per-request callers (context
    # processor, mixins, views) share one query; User objects never outlive
    # the request, so this cannot go stale across requests.
    cached = getattr(user, "_clubhub_person", None)
    if cached is not None and cached.user_id == user.pk:
        return cached
    try:
        # club + staff_profile are read on every rendered request (theming,
        # sidebar admin links) — preload them alongside the person.
        person = Person.objects.select_related("club", "staff_profile").get(user=user)
    except Person.DoesNotExist:
        return None
    user._clubhub_person = person
    return person


def has_staff_profile(user):
    person = get_person(user)
    return bool(person) and hasattr(person, "staff_profile")


def is_admin(user):
    person = get_person(user)
    profile = getattr(person, "staff_profile", None) if person else None
    return bool(profile and profile.is_admin)


def trainer_group_ids(user):
    person = get_person(user)
    if person is None:
        return set()
    return set(
        GroupMembership.objects.filter(
            person=person,
            role=GroupMembership.Role.TRAINER,
            left_on__isnull=True,
        ).values_list("group_id", flat=True)
    )


def visible_groups(user):
    person = get_person(user)
    if person is None:
        return Group.objects.none()
    groups = Group.objects.filter(club=person.club)
    if is_admin(user):
        return groups
    return groups.filter(id__in=trainer_group_ids(user))


def visible_activities(user):
    return Activity.objects.filter(group__in=visible_groups(user))


def can_manage_group(user, group):
    return visible_groups(user).filter(pk=group.pk).exists()

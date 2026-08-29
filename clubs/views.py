from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordChangeView
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import UpdateView

from .translations import (
    LANGUAGE_NAMES,
    available_languages,
    reset_language_cache,
    translate,
)

from people import services
from people.mixins import AdminRequiredMixin
from people.models import Membership, StaffProfile
from scheduling.models import Activity

from .forms import ClubSettingsForm, UserPasswordChangeForm, UserSettingsForm
from .models import Club, UserProfile


@login_required
def home(request):
    person = services.get_person(request.user)
    if person is None:
        return render(request, "clubs/no_profile.html", status=403)
    today = timezone.localdate()
    groups = services.visible_groups(request.user)
    todays_activities = (
        Activity.objects.filter(group__in=groups, date=today)
        .select_related("group")
        .order_by("start_time")
    )
    upcoming_activities = (
        Activity.objects.filter(
            group__in=groups, date__gt=today, date__lte=today + timedelta(days=7)
        )
        .select_related("group")
        .order_by("date", "start_time")[:8]
    )
    context = {
        "person": person,
        "today": today,
        "todays_activities": todays_activities,
        "upcoming_activities": upcoming_activities,
    }
    if services.is_admin(request.user):
        context["stats"] = {
            translate("Aktiva medlemmar", "Startsida"): Membership.objects.filter(
                person__club=person.club, status=Membership.Status.ACTIVE
            ).count(),
            translate("Obetalda", "Startsida"): Membership.objects.filter(
                person__club=person.club, payment_status=Membership.PaymentStatus.UNPAID
            ).count(),
            translate("Ledare", "Startsida"): StaffProfile.objects.filter(
                person__club=person.club
            ).count(),
            translate("Grupp", "Allmän"): groups.count(),
        }
    return render(request, "clubs/dashboard.html", context)


class ClubSettingsView(AdminRequiredMixin, UpdateView):
    model = Club
    form_class = ClubSettingsForm
    template_name = "clubs/settings.html"

    def get_object(self):
        return services.get_person(self.request.user).club

    def get_success_url(self):
        return reverse_lazy("clubs:settings")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            translate("Inställningarna har sparats.", "Klubbinställningar"),
        )
        return response


@login_required
def remove_club_image(request):
    person = services.get_person(request.user)
    if person is None or not services.is_admin(request.user):
        return JsonResponse({"error": "forbidden"}, status=403)
    field = request.POST.get("field")
    if field not in ("logo", "background_image"):
        return JsonResponse({"error": "unknown field"}, status=400)
    club = person.club
    image = getattr(club, field)
    if image:
        image.delete(save=False)
        setattr(club, field, "")
        club.save()
    return JsonResponse({"ok": True})


def _profile_for(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def _user_settings_context(request, **overrides):
    profile = _profile_for(request.user)
    form = overrides.pop("profile_form", None) or UserSettingsForm()
    # Current values shown as placeholders; empty fields keep the stored value on save.
    person = getattr(request.user, "person", None)
    placeholders = {
        "first_name": request.user.first_name or (person.first_name if person else ""),
        "last_name": request.user.last_name or (person.last_name if person else ""),
        "email": request.user.email or (person.email if person else ""),
    }
    for name, value in placeholders.items():
        if value:
            form.fields[name].widget.attrs["placeholder"] = value
    context = {
        "profile_form": form,
        "language": profile.language,
        "language_choices": [("", translate("Standard", "Inställningar"))]
        + [(code, LANGUAGE_NAMES.get(code, code)) for code in available_languages()],
        "password_form": overrides.pop("password_form", None)
        or UserPasswordChangeForm(request.user),
    }
    context.update(overrides)
    return context


@login_required
def user_settings(request):
    if request.method == "POST":
        if request.POST.get("form") == "language":
            language = request.POST.get("language", "")
            if language == "" or language in available_languages():
                profile = _profile_for(request.user)
                profile.language = language
                profile.save()
                reset_language_cache(request)
                messages.success(
                    request, translate("Inställningarna har sparats.", "Inställningar")
                )
            return redirect("clubs:user_settings")
        form = UserSettingsForm(request.POST)
        if form.is_valid():
            form.save(request.user)
            messages.success(
                request, translate("Inställningarna har sparats.", "Inställningar")
            )
            return redirect("clubs:user_settings")
        return render(
            request,
            "clubs/user_settings.html",
            _user_settings_context(request, profile_form=form),
        )
    return render(request, "clubs/user_settings.html", _user_settings_context(request))


class UserPasswordChangeView(PasswordChangeView):
    """Password change living on the /settings/ page instead of the old
    standalone /accounts/password_change/ page."""

    template_name = "clubs/user_settings.html"
    form_class = UserPasswordChangeForm
    success_url = reverse_lazy("clubs:user_settings")

    def get_context_data(self, **kwargs):
        return _user_settings_context(self.request, password_form=kwargs["form"])

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, translate("Lösenordet har ändrats.", "Konton"))
        return response

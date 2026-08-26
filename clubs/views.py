from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import UpdateView

from .translations import translate

from people import services
from people.mixins import AdminRequiredMixin
from people.models import Membership, StaffProfile
from scheduling.models import Activity

from .forms import ClubSettingsForm
from .models import Club


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

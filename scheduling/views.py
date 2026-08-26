from datetime import date as date_cls
from datetime import timedelta

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import (
    CreateView,
    DeleteView,
    ListView,
    UpdateView,
)

from clubs.translations import translate
from people import services
from people.mixins import StaffRequiredMixin

from .forms import ActivityForm, ActivityTemplateForm, SeasonForm
from .models import Activity, ActivityTemplate, Season
from .services import generate_occurrences, regenerate_occurrences


class SeasonListView(StaffRequiredMixin, ListView):
    template_name = "scheduling/season_list.html"
    context_object_name = "seasons"

    def get_queryset(self):
        person = services.get_person(self.request.user)
        return Season.objects.filter(club=person.club).order_by("-start_date")


class SeasonCreateView(StaffRequiredMixin, CreateView):
    model = Season
    form_class = SeasonForm
    template_name = "shared/object_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Ny säsong"
        context["cancel_url"] = reverse_lazy("schedule:season_list")
        return context

    def form_valid(self, form):
        form.instance.club = services.get_person(self.request.user).club
        response = super().form_valid(form)
        messages.success(self.request, translate("Säsongen har skapats.", "Schema"))
        return response

    def get_success_url(self):
        return reverse_lazy("schedule:season_list")


class SeasonUpdateView(StaffRequiredMixin, UpdateView):
    form_class = SeasonForm
    template_name = "shared/object_form.html"

    def get_queryset(self):
        person = services.get_person(self.request.user)
        return Season.objects.filter(club=person.club)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = f"Ändra säsongen {self.object.name}"
        context["cancel_url"] = reverse_lazy("schedule:season_list")
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, translate("Säsongen har uppdaterats.", "Schema"))
        return response

    def get_success_url(self):
        return reverse_lazy("schedule:season_list")


class TemplateListView(StaffRequiredMixin, ListView):
    template_name = "scheduling/template_list.html"
    context_object_name = "templates"

    def get_queryset(self):
        person = services.get_person(self.request.user)
        queryset = ActivityTemplate.objects.filter(club=person.club).select_related(
            "group", "season"
        )
        season_id = self.request.GET.get("season")
        if season_id:
            queryset = queryset.filter(season_id=season_id)
        return queryset.order_by("season__start_date", "weekday", "start_time")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        person = services.get_person(self.request.user)
        context["seasons"] = Season.objects.filter(club=person.club).order_by("-start_date")
        try:
            context["selected_season"] = int(self.request.GET.get("season") or 0)
        except ValueError:
            context["selected_season"] = None
        return context


class TemplateMixin:
    def get_queryset(self):
        person = services.get_person(self.request.user)
        return ActivityTemplate.objects.filter(club=person.club)


class TemplateCreateView(TemplateMixin, StaffRequiredMixin, CreateView):
    form_class = ActivityTemplateForm
    template_name = "shared/object_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Ny aktivitetsmall"
        context["cancel_url"] = reverse_lazy("schedule:template_list")
        return context

    def form_valid(self, form):
        form.instance.club = services.get_person(self.request.user).club
        self.object = form.save()
        created = generate_occurrences(self.object)
        messages.success(
            self.request,
            f"{translate('Mallen sparades.', 'Schema')} {len(created)} "
            f"{translate('aktiviteter skapades.', 'Schema')}",
        )
        return redirect(reverse_lazy("schedule:template_list"))


class TemplateUpdateView(TemplateMixin, StaffRequiredMixin, UpdateView):
    form_class = ActivityTemplateForm
    template_name = "shared/object_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = f"Ändra mall: {self.object.title}"
        context["cancel_url"] = reverse_lazy("schedule:template_list")
        return context

    def form_valid(self, form):
        self.object = form.save()
        deleted_count, created_count = regenerate_occurrences(self.object)
        messages.success(
            self.request,
            f"{translate('Mallen sparades och framtida pass har uppdaterats.', 'Schema')} "
            f"{translate('Pass med registrerad närvaro och manuellt ändrade pass påverkas inte.', 'Schema')}",
        )
        return redirect(reverse_lazy("schedule:template_list"))


class TemplateDeleteView(TemplateMixin, StaffRequiredMixin, DeleteView):
    template_name = "shared/confirm_delete.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["cancel_url"] = reverse_lazy("schedule:template_list")
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            translate(
                "Mallen togs bort. Befintliga pass behålls som enskilda aktiviteter.",
                "Schema",
            ),
        )
        return response

    def get_success_url(self):
        return reverse_lazy("schedule:template_list")


class ScheduleWeekView(StaffRequiredMixin, ListView):
    template_name = "scheduling/schedule_week.html"
    context_object_name = "activities"

    def _week_start(self):
        raw = self.request.GET.get("date")
        try:
            selected = date_cls.fromisoformat(raw) if raw else timezone.localdate()
        except ValueError:
            selected = timezone.localdate()
        return selected - timedelta(days=selected.weekday())

    def get_queryset(self):
        week_start = self._week_start()
        return (
            services.visible_activities(self.request.user)
            .filter(date__gte=week_start, date__lte=week_start + timedelta(days=6))
            .select_related("group")
            .order_by("date", "start_time")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        week_start = self._week_start()
        days = []
        activities = list(context["activities"])
        for offset in range(7):
            day = week_start + timedelta(days=offset)
            days.append(
                {
                    "date": day,
                    "is_today": day == today,
                    "activities": [a for a in activities if a.date == day],
                }
            )
        context.update(
            {
                "days": days,
                "today": today,
                "prev_week": (week_start - timedelta(days=7)).isoformat(),
                "next_week": (week_start + timedelta(days=7)).isoformat(),
                "week_start": week_start,
                "week_end": week_start + timedelta(days=6),
            }
        )
        return context


class ActivityMixin:
    def get_queryset(self):
        return services.visible_activities(self.request.user)


class ActivityCreateView(ActivityMixin, StaffRequiredMixin, CreateView):
    model = Activity
    form_class = ActivityForm
    template_name = "shared/object_form.html"

    def get_initial(self):
        initial = super().get_initial()
        initial.setdefault("date", timezone.localdate())
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Nytt enskilt pass"
        context["cancel_url"] = reverse_lazy("schedule:week")
        return context

    def form_valid(self, form):
        form.instance.club = services.get_person(self.request.user).club
        form.instance.is_manually_edited = True
        response = super().form_valid(form)
        messages.success(
            self.request, translate("Aktiviteten har skapats.", "Schema")
        )
        return response

    def get_success_url(self):
        return reverse_lazy("schedule:week")


class ActivityUpdateView(ActivityMixin, StaffRequiredMixin, UpdateView):
    form_class = ActivityForm
    template_name = "shared/object_form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = f"Ändra pass: {self.object.title} {self.object.date}"
        context["cancel_url"] = reverse_lazy("schedule:week")
        return context

    def form_valid(self, form):
        form.instance.is_manually_edited = True
        response = super().form_valid(form)
        messages.success(
            self.request,
            translate(
                "Aktiviteten har uppdaterats. Den följer inte längre mallens återkommande schema.",
                "Schema",
            ),
        )
        return response

    def get_success_url(self):
        return reverse_lazy("schedule:week")


class ActivityDeleteView(ActivityMixin, StaffRequiredMixin, DeleteView):
    template_name = "shared/confirm_delete.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["cancel_url"] = reverse_lazy("schedule:week")
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, translate("Aktiviteten har tagits bort.", "Schema"))
        return response

    def get_success_url(self):
        return reverse_lazy("schedule:week")

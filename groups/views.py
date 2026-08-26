from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Count, ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from clubs.translations import translate
from people import services
from people.mixins import StaffRequiredMixin

from .forms import GroupForm, GroupMembershipForm
from .models import Group, GroupMembership


class GroupListView(StaffRequiredMixin, ListView):
    template_name = "groups/group_list.html"
    context_object_name = "groups"

    def get_queryset(self):
        return (
            services.visible_groups(self.request.user)
            .annotate(
                member_count=Count(
                    "memberships",
                    filter=Q(
                        memberships__role=GroupMembership.Role.MEMBER,
                        memberships__left_on__isnull=True,
                    ),
                ),
                trainer_count=Count(
                    "memberships",
                    filter=Q(
                        memberships__role=GroupMembership.Role.TRAINER,
                        memberships__left_on__isnull=True,
                    ),
                ),
            )
            .order_by("name")
        )


class GroupDetailView(StaffRequiredMixin, DetailView):
    context_object_name = "group"

    def get_queryset(self):
        return services.visible_groups(self.request.user).prefetch_related(
            "memberships__person"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        context["memberships"] = (
            self.object.memberships.filter(left_on__isnull=True)
            .select_related("person")
            .order_by("role", "person__last_name")
        )
        context["membership_form"] = GroupMembershipForm(
            club=self.object.club, group=self.object
        )
        context["upcoming_activities"] = (
            self.object.activities.filter(date__gte=today)
            .order_by("date", "start_time")[:10]
        )
        return context


class GroupCreateView(StaffRequiredMixin, CreateView):
    model = Group
    form_class = GroupForm
    template_name = "shared/object_form.html"
    success_url = reverse_lazy("groups:list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Ny grupp"
        context["cancel_url"] = reverse_lazy("groups:list")
        return context

    def form_valid(self, form):
        form.instance.club = services.get_person(self.request.user).club
        response = super().form_valid(form)
        messages.success(self.request, translate("Gruppen har skapats.", "Grupper"))
        return response


class GroupUpdateView(StaffRequiredMixin, UpdateView):
    form_class = GroupForm
    template_name = "shared/object_form.html"
    context_object_name = "group"

    def get_queryset(self):
        return services.visible_groups(self.request.user)

    def get_success_url(self):
        return reverse_lazy("groups:detail", kwargs={"pk": self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = f"Ändra gruppen {self.object.name}"
        context["cancel_url"] = reverse_lazy("groups:detail", kwargs={"pk": self.object.pk})
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, translate("Gruppen har uppdaterats.", "Grupper"))
        return response


class GroupDeleteView(StaffRequiredMixin, DeleteView):
    template_name = "shared/confirm_delete.html"
    success_url = reverse_lazy("groups:list")

    def get_queryset(self):
        return services.visible_groups(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["cancel_url"] = reverse_lazy("groups:list")
        return context

    def form_valid(self, form):
        try:
            response = super().form_valid(form)
        except ProtectedError:
            messages.error(
                self.request,
                translate(
                    "Gruppen kan inte tas bort eftersom den har aktiviteter.", "Grupper"
                ),
            )
            return redirect(self.success_url)
        messages.success(self.request, translate("Gruppen har tagits bort.", "Grupper"))
        return response


@require_POST
def membership_add(request, pk):
    group = get_object_or_404(services.visible_groups(request.user), pk=pk)
    form = GroupMembershipForm(request.POST, club=group.club, group=group)
    if form.is_valid():
        membership = GroupMembership(
            group=group,
            person=form.cleaned_data["person"],
            role=form.cleaned_data["role"],
        )
        try:
            membership.full_clean(exclude=["joined_on"])
            membership.save()
            messages.success(
                self.request, translate("Personen är tillagd.", "Grupper")
            )
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
    else:
        messages.error(
            request, translate("Kunde inte lägga till personen.", "Grupper")
        )
    return redirect("groups:detail", pk=pk)


@require_POST
def membership_remove(request, pk, member_pk):
    group = get_object_or_404(services.visible_groups(request.user), pk=pk)
    membership = get_object_or_404(
        group.memberships, person_id=member_pk, left_on__isnull=True
    )
    membership.left_on = timezone.localdate()
    membership.save()
    messages.success(request, translate("Personen har lämnat gruppen.", "Grupper"))
    return redirect("groups:detail", pk=pk)

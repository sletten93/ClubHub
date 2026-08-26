from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import DetailView, FormView, ListView

from clubs.translations import translate
from people import services
from people.mixins import StaffRequiredMixin

from .forms import NotificationForm
from .models import Notification
from .services import register_recipients, send_notification


class NotificationListView(StaffRequiredMixin, ListView):
    template_name = "notifications/notification_list.html"
    context_object_name = "notifications"

    def get_queryset(self):
        person = services.get_person(self.request.user)
        return Notification.objects.filter(club=person.club).select_related("created_by")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["compose_url"] = reverse_lazy("notifications:compose")
        return context


class NotificationDetailView(StaffRequiredMixin, DetailView):
    template_name = "notifications/notification_detail.html"
    context_object_name = "notification"

    def get_queryset(self):
        person = services.get_person(self.request.user)
        return Notification.objects.filter(club=person.club)


class NotificationComposeView(StaffRequiredMixin, FormView):
    form_class = NotificationForm
    template_name = "notifications/notification_form.html"
    success_url = reverse_lazy("notifications:list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["club"] = services.get_person(self.request.user).club
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Nytt meddelande"
        context["cancel_url"] = reverse_lazy("notifications:list")
        return context

    def form_valid(self, form):
        person = services.get_person(self.request.user)
        data = form.cleaned_data
        notification = Notification.objects.create(
            club=person.club,
            subject=data["subject"],
            body=data["body"],
            all_members=(data["audience"] == "all"),
            created_by=person,
        )
        if data.get("groups"):
            notification.groups.set(data["groups"])
        register_recipients(notification)
        sent = send_notification(notification)
        total = notification.recipients.count()
        messages.success(
            self.request,
            f"{translate('Meddelandet har skickats.', 'Meddelanden')} "
            f"({sent}/{total} {translate('Mottagare', 'Meddelanden').lower()}).",
        )
        return redirect("notifications:detail", pk=notification.pk)

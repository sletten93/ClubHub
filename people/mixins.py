from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

from . import services


class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return services.has_staff_profile(self.request.user)


class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return services.is_admin(self.request.user)

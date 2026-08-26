from django.contrib import admin

from .models import AdminGroup, GuardianRelation, Membership, Person, StaffProfile


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ("last_name", "first_name", "club", "gender", "email", "phone_mobile")
    list_filter = ("club", "gender")
    search_fields = ("first_name", "last_name", "personnummer", "email")


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("person", "status", "payment_status", "start_date", "photo_consent")
    list_filter = ("status", "payment_status")
    search_fields = ("person__first_name", "person__last_name")


@admin.register(GuardianRelation)
class GuardianRelationAdmin(admin.ModelAdmin):
    list_display = ("guardian", "child")
    search_fields = (
        "guardian__first_name",
        "guardian__last_name",
        "child__first_name",
        "child__last_name",
    )


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display = ("person", "is_admin")
    list_filter = ("is_admin",)
    search_fields = ("person__first_name", "person__last_name")


@admin.register(AdminGroup)
class AdminGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "club")
    list_filter = ("club",)
    search_fields = ("name",)

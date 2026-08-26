from django.contrib import admin

from .models import Group, GroupMembership


class GroupMembershipInline(admin.TabularInline):
    model = GroupMembership
    extra = 0


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ("name", "club")
    list_filter = ("club",)
    search_fields = ("name",)
    inlines = [GroupMembershipInline]


@admin.register(GroupMembership)
class GroupMembershipAdmin(admin.ModelAdmin):
    list_display = ("person", "group", "role", "joined_on", "left_on")
    list_filter = ("group", "role")
    search_fields = ("person__first_name", "person__last_name", "group__name")

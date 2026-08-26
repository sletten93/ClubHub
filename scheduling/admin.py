from django.contrib import admin

from .models import Activity, ActivityTemplate, Season


@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    list_display = ("name", "club", "start_date", "end_date")
    list_filter = ("club",)
    search_fields = ("name",)


@admin.register(ActivityTemplate)
class ActivityTemplateAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "season",
        "group",
        "activity_type",
        "recurrence",
        "weekday",
        "start_time",
        "location",
        "is_active",
    )
    list_filter = ("activity_type", "recurrence", "season", "is_active")
    search_fields = ("title",)


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "date",
        "start_time",
        "end_time",
        "group",
        "activity_type",
        "location",
        "is_cancelled",
    )
    list_filter = ("activity_type", "is_cancelled", "season", "group")
    search_fields = ("title",)
    date_hierarchy = "date"

from django.contrib import admin

from .models import AttendanceRecord


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ("person", "activity", "status", "registered_by", "updated_at")
    list_filter = ("status", "activity__group")
    search_fields = ("person__first_name", "person__last_name", "activity__title")

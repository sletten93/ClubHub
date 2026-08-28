from django.contrib import admin

from .models import Club, UserProfile


@admin.register(Club)
class ClubAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "email", "city")
    search_fields = ("name", "slug")


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "language")
    search_fields = ("user__username",)

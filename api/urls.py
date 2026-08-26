from django.urls import path

from . import views

app_name = "api"

urlpatterns = [
    path('clubs/', views.ClubListAPIView.as_view(), name='club_list'),
    path('clubs/<slug:slug>/schedule/', views.ClubScheduleAPIView.as_view(), name='club_schedule'),
    path('clubs/<slug:slug>/groups/', views.ClubGroupsAPIView.as_view(), name='club_groups'),
    path('clubs/<slug:slug>/seasons/', views.ClubSeasonsAPIView.as_view(), name='club_seasons'),
]

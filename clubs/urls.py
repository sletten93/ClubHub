from django.urls import path

from . import views

app_name = "clubs"

urlpatterns = [
    path('', views.home, name='home'),
    path('clubsettings/', views.ClubSettingsView.as_view(), name='settings'),
    path('clubsettings/remove-image/', views.remove_club_image, name='remove_image'),
]

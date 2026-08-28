from django.urls import path

from . import views

app_name = "clubs"

urlpatterns = [
    path('', views.home, name='home'),
    path('settings/', views.user_settings, name='user_settings'),
    path('settings/password/', views.UserPasswordChangeView.as_view(), name='user_password'),
    path('clubsettings/', views.ClubSettingsView.as_view(), name='settings'),
    path('clubsettings/remove-image/', views.remove_club_image, name='remove_image'),
]

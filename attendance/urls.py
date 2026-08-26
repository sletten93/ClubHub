from django.urls import path

from . import views

app_name = "attendance"

urlpatterns = [
    path('activity/<int:pk>/', views.TakeAttendanceView.as_view(), name='take'),
    path('activity/<int:pk>/record/<int:person_pk>/', views.record_update, name='record'),
    path('activity/<int:pk>/bulk-present/', views.bulk_present, name='bulk_present'),
]

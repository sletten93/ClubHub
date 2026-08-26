from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path('', views.NotificationListView.as_view(), name='list'),
    path('new/', views.NotificationComposeView.as_view(), name='compose'),
    path('<int:pk>/', views.NotificationDetailView.as_view(), name='detail'),
]

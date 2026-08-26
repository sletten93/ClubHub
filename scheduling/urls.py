from django.urls import path

from . import views

app_name = "schedule"

urlpatterns = [
    path('', views.ScheduleWeekView.as_view(), name='week'),
    path('seasons/', views.SeasonListView.as_view(), name='season_list'),
    path('seasons/new/', views.SeasonCreateView.as_view(), name='season_create'),
    path('seasons/<int:pk>/update/', views.SeasonUpdateView.as_view(), name='season_update'),
    path('templates/', views.TemplateListView.as_view(), name='template_list'),
    path('templates/new/', views.TemplateCreateView.as_view(), name='template_create'),
    path('templates/<int:pk>/update/', views.TemplateUpdateView.as_view(), name='template_update'),
    path('templates/<int:pk>/delete/', views.TemplateDeleteView.as_view(), name='template_delete'),
    path('activities/new/', views.ActivityCreateView.as_view(), name='activity_create'),
    path('activities/<int:pk>/update/', views.ActivityUpdateView.as_view(), name='activity_update'),
    path('activities/<int:pk>/delete/', views.ActivityDeleteView.as_view(), name='activity_delete'),
]

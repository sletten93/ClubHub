from django.urls import path

from . import views

app_name = "groups"

urlpatterns = [
    path('', views.GroupListView.as_view(), name='list'),
    path('new/', views.GroupCreateView.as_view(), name='create'),
    path('<int:pk>/', views.GroupDetailView.as_view(), name='detail'),
    path('<int:pk>/update/', views.GroupUpdateView.as_view(), name='update'),
    path('<int:pk>/delete/', views.GroupDeleteView.as_view(), name='delete'),
    path('<int:pk>/members/add/', views.membership_add, name='membership_add'),
    path(
        '<int:pk>/members/<int:member_pk>/remove/',
        views.membership_remove,
        name='membership_remove',
    ),
]

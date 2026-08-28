from django.urls import path

from . import views

app_name = "people"

urlpatterns = [
    path('', views.PersonRegisterView.as_view(), name='register'),
    path('new/', views.PersonCreateView.as_view(), name='create'),
    path('<int:pk>/update/', views.PersonUpdateView.as_view(), name='update'),
    path('<int:pk>/delete/', views.PersonDeleteView.as_view(), name='delete'),
    path('import/', views.PersonImportPreviewView.as_view(), name='import_preview'),
    path('import/confirm/', views.PersonImportConfirmView.as_view(), name='import_confirm'),
    path('export/', views.PersonExportView.as_view(), name='export'),
]

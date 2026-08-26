from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path('', views.InvoiceListView.as_view(), name='list'),
    path('<int:pk>/', views.InvoiceDetailView.as_view(), name='detail'),
    path('<int:pk>/payments/add/', views.register_payment, name='add_payment'),
]

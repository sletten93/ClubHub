from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

handler404 = 'config.views.handler404'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', include('clubs.urls')),
    path('groups/', include('groups.urls')),
    path('registry/', include('people.urls')),
    path('schedule/', include('scheduling.urls')),
    path('attendance/', include('attendance.urls')),
    path('invoices/', include('payments.urls')),
    path('messages/', include('notifications.urls')),
    path('api/', include('api.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

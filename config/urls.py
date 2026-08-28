from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

handler404 = 'config.views.handler404'

urlpatterns = [
    path('admin/', admin.site.urls),
    # The password change moved to /settings/; keep old links working.
    path('accounts/password_change/',
         RedirectView.as_view(pattern_name='clubs:user_settings'), name='password_change_redirect'),
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

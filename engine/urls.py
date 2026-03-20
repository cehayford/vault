from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.i18n import set_language


static_path_media = static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
static_path = static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('i18n/setlang/', set_language, name='set_language'),
    path('', include('userauth.urls')),
    path('voting/', include('voting.urls')),
    path('nominee/', include('nominee.urls')),
    path('accounts/', include('allauth.urls')),
] + static_path + static_path_media

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
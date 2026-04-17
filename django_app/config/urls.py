from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static

from callpower.apps.api.views import AdminAppView


urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("", include("callpower.apps.auth.urls")),
    path("api/", include("callpower.apps.api.urls")),
    path("call/", include("callpower.apps.calls.urls")),
    path("political_data/", include("callpower.apps.political_data.urls")),
    path("admin/", AdminAppView.as_view(), name="admin-app"),
    path("", include("callpower.apps.public.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

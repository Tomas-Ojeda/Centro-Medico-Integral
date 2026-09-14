from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

urlpatterns = [
    path('', lambda req: redirect('dashboard:index'), name='home'),
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('dashboard/', include('dashboard.urls', namespace='dashboard')),
    path('pacientes/', include('pacientes.urls', namespace='pacientes')),
    path('profesionales/', include('profesionales.urls', namespace='profesionales')),
    path('turnos/', include('turnos.urls', namespace='turnos')),
    path('historias/', include('historias.urls', namespace='historias')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

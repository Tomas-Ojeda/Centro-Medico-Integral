"""Control de acceso global por rol.

Deniega por defecto a cualquier usuario autenticado que no sea
Administrador, Recepción o Profesional. El login, el logout, los archivos
estáticos y el admin (solo superusuarios) quedan fuera del bloqueo.
"""

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.views.defaults import permission_denied

from .permisos import (
    MENSAJE_SIN_ROL,
    es_admin,
    es_profesional,
    es_recepcion,
)


class RolRequeridoMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user

        if not user.is_authenticated:
            return self.get_response(request)

        path = request.path_info

        # El admin de Django queda reservado a superusuarios.
        admin_path = reverse('admin:index')
        if path.startswith(admin_path):
            if es_admin(user):
                return self.get_response(request)
            return permission_denied(request, PermissionDenied(
                'El panel de administración es solo para administradores.'
            ))

        # Login/logout deben seguir accesibles para poder entrar o salir.
        if (
            path.startswith(reverse('login'))
            or path.startswith(reverse('logout'))
        ):
            return self.get_response(request)

        # Archivos estáticos del admin/login.
        static_url = getattr(settings, 'STATIC_URL', None)
        if static_url and path.startswith(static_url):
            return self.get_response(request)

        if es_admin(user) or es_recepcion(user) or es_profesional(user):
            return self.get_response(request)

        return permission_denied(request, PermissionDenied(MENSAJE_SIN_ROL))

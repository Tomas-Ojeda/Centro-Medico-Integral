"""Roles y permisos centralizados del sistema.

Roles:
  - Administrador: superusuario de Django. Acceso total.
  - Recepción: grupo ``Recepcion``. Acceso completo a la operación diaria.
  - Profesional: grupo ``Profesional``. Acceso limitado a sus pacientes y turnos.

Un usuario que pertenezca a ``Recepcion`` y ``Profesional`` a la vez se trata
como Recepción (el rol operativo más amplio). Un usuario sin ninguno de estos
roles es rechazado por el middleware global.
"""

from django.core.exceptions import PermissionDenied

GRUPO_RECEPCION = 'Recepcion'
GRUPO_PROFESIONAL = 'Profesional'

MENSAJE_SIN_ROL = (
    'Tu usuario no tiene un rol asignado. '
    'Contactá a recepción para que te asignen un rol.'
)
MENSAJE_SIN_PROFESIONAL = (
    'Tu usuario no está vinculado a un profesional, contactá a recepción.'
)


def _autenticado(user):
    return bool(user and getattr(user, 'is_authenticated', False))


def _tiene_grupo(user, nombre):
    return _autenticado(user) and user.groups.filter(name=nombre).exists()


def es_admin(user):
    """Administrador = superusuario de Django."""
    return bool(_autenticado(user) and user.is_superuser)


def es_recepcion(user):
    """Administrador o usuario del grupo Recepcion."""
    return es_admin(user) or _tiene_grupo(user, GRUPO_RECEPCION)


def es_profesional(user):
    """Usuario del grupo Profesional que no tenga además rol de Recepción."""
    return (
        _autenticado(user)
        and not es_recepcion(user)
        and _tiene_grupo(user, GRUPO_PROFESIONAL)
    )


def rol_usuario(user):
    if es_admin(user):
        return 'Administrador'
    if es_recepcion(user):
        return 'Recepción'
    if es_profesional(user):
        return 'Profesional'
    return 'Sin rol'


def profesional_actual(user):
    """Devuelve el Profesional vinculado al usuario, o None."""
    if not es_profesional(user):
        return None
    # Import local para evitar ciclos durante la carga de apps.
    from profesionales.models import Profesional

    return Profesional.objects.filter(usuario=user).first()


class SoloRecepcionMixin:
    """Permite el acceso únicamente a Administrador y Recepción."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not es_recepcion(request.user):
            raise PermissionDenied(
                'Esta sección es solo para recepción o administración.'
            )
        return super().dispatch(request, *args, **kwargs)


class RecepcionOProfesionalMixin:
    """Permite Administrador/Recepción y profesionales vinculados.

    Deja en ``self.profesional`` el Profesional del usuario (o None para
    recepción/administración), para que las vistas filtren sus datos.
    """

    profesional = None

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if user.is_authenticated:
            if es_recepcion(user):
                self.profesional = None
            elif es_profesional(user):
                self.profesional = profesional_actual(user)
                if self.profesional is None:
                    raise PermissionDenied(MENSAJE_SIN_PROFESIONAL)
            else:
                raise PermissionDenied(MENSAJE_SIN_ROL)
        return super().dispatch(request, *args, **kwargs)

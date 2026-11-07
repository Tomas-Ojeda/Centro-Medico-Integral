from django.conf import settings

from .permisos import (
    es_admin,
    es_profesional,
    es_recepcion,
    profesional_actual,
    rol_usuario,
)


def nombre_centro(request):
    """Expone el nombre visible del centro a todas las plantillas."""
    return {
        'NOMBRE_CENTRO': settings.NOMBRE_CENTRO,
        'NOMBRE_CENTRO_TITULO': settings.NOMBRE_CENTRO_TITULO,
        'NOMBRE_CENTRO_LOCALIDAD': settings.NOMBRE_CENTRO_LOCALIDAD,
    }


def roles(request):
    """Expone el rol del usuario y sus permisos básicos a las plantillas."""
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {
            'rol_usuario': '',
            'es_admin': False,
            'es_recepcion': False,
            'es_profesional': False,
            'profesional_actual': None,
            'pagos_visibles_profesional': settings.PAGOS_VISIBLES_PARA_PROFESIONAL,
            'profesional_puede_llamar_paciente': (
                settings.PROFESIONAL_PUEDE_LLAMAR_PACIENTE
            ),
            'solicitudes_pendientes_count': 0,
            'derivaciones_pendientes_count': 0,
        }

    recepcion = es_recepcion(user)
    profesional = profesional_actual(user)

    solicitudes_pendientes = 0
    if recepcion:
        # Una sola consulta y solo para quienes ven la cola de trabajo.
        from turnos.models import EstadoSolicitud, SolicitudTurno

        solicitudes_pendientes = SolicitudTurno.objects.filter(
            estado=EstadoSolicitud.PENDIENTE
        ).count()

    derivaciones_pendientes = 0
    if profesional is not None:
        # Una sola consulta: notificación del profesional destino.
        from derivaciones.models import Derivacion, EstadoDerivacion

        derivaciones_pendientes = Derivacion.objects.filter(
            profesional_destino=profesional,
            estado=EstadoDerivacion.PENDIENTE,
        ).count()

    return {
        'rol_usuario': rol_usuario(user),
        'es_admin': es_admin(user),
        'es_recepcion': recepcion,
        'es_profesional': es_profesional(user),
        'profesional_actual': profesional,
        'pagos_visibles_profesional': settings.PAGOS_VISIBLES_PARA_PROFESIONAL,
        'profesional_puede_llamar_paciente': (
            settings.PROFESIONAL_PUEDE_LLAMAR_PACIENTE
        ),
        'solicitudes_pendientes_count': solicitudes_pendientes,
        'derivaciones_pendientes_count': derivaciones_pendientes,
    }

from ipware import get_client_ip
from .models import LogAcceso


class AuditoriaMixin:
    """Mixin para registrar accesos en las vistas."""

    accion = None  # 'ver', 'crear', 'editar', 'borrar', 'descargar', 'exportar', 'importar'
    modelo = None  # 'Paciente', 'Consulta', 'Turno', 'Profesional'

    def registrar_acceso(self, request, objeto=None, accion=None, detalle='', modelo=None):
        """Registra un acceso en el log de auditoría."""
        ip, _ = get_client_ip(request, proxy_count=1)
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]

        LogAcceso.objects.create(
            usuario=request.user if request.user.is_authenticated else None,
            accion=accion or self.accion,
            modelo=modelo or self.modelo or '',
            objeto_id=objeto.pk if objeto else None,
            ip=ip,
            user_agent=user_agent,
            detalle=detalle or '',
        )

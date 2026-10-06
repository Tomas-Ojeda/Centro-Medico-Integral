from .models import LogAcceso


class AuditoriaMixin:
    """Mixin para registrar accesos en las vistas."""

    accion = None  # 'ver', 'crear', 'editar', 'borrar', 'descargar', 'exportar', 'importar'
    modelo = None  # 'Paciente', 'Consulta', 'Turno', 'Profesional'

    def registrar_acceso(self, request, objeto=None, accion=None):
        """Registra un acceso en el log de auditoría."""
        ip = self._obtener_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]

        LogAcceso.objects.create(
            usuario=request.user if request.user.is_authenticated else None,
            accion=accion or self.accion,
            modelo=self.modelo or '',
            objeto_id=objeto.pk if objeto else None,
            ip=ip,
            user_agent=user_agent
        )

    def _obtener_ip(self, request):
        """Obtiene la IP real del usuario, respetando X-Forwarded-For solo si viene del proxy de confianza."""
        # En Render, el proxy es de confianza y setea X-Forwarded-For
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            # La primera IP en X-Forwarded-For es la del cliente
            ip = x_forwarded_for.split(',')[0].strip()
            return ip
        return request.META.get('REMOTE_ADDR')

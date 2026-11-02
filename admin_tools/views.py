import os
import tempfile
import zipfile
from pathlib import Path

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.http import FileResponse
from django.utils import timezone
from django.views import View

from auditoria.mixins import AuditoriaMixin


class SoloSuperusuarioMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Permite el acceso solo a superusuarios.

    Los usuarios autenticados sin permiso reciben un 403; los anónimos son
    redirigidos al login.
    """

    def test_func(self):
        return self.request.user.is_superuser

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied(
                'Esta sección es solo para administradores.'
            )
        return super().handle_no_permission()


def generar_zip_adjuntos(media_root):
    """Arma un ZIP con todos los archivos bajo ``media_root``.

    Escribe en un archivo temporal para no cargar los adjuntos en memoria.
    Devuelve ``(archivo_temporal, cantidad_archivos, total_bytes)``. El
    llamador es responsable de cerrar el archivo (FileResponse lo hace al
    terminar de enviarlo).
    """
    media_root = Path(media_root).resolve()
    archivo_temporal = tempfile.TemporaryFile()
    cantidad = 0
    total_bytes = 0

    try:
        with zipfile.ZipFile(
            archivo_temporal,
            'w',
            zipfile.ZIP_DEFLATED,
            allowZip64=True,
        ) as archivo_zip:
            if media_root.is_dir():
                for dirpath, dirnames, filenames in os.walk(
                    media_root,
                    followlinks=False,
                ):
                    # No seguir enlaces simbólicos: podrían apuntar fuera
                    # de MEDIA_ROOT.
                    dirnames[:] = sorted(
                        nombre
                        for nombre in dirnames
                        if not (Path(dirpath) / nombre).is_symlink()
                    )

                    for nombre in sorted(filenames):
                        ruta = Path(dirpath) / nombre
                        if ruta.is_symlink() or not ruta.is_file():
                            continue
                        try:
                            relativa = ruta.relative_to(media_root)
                        except ValueError:
                            continue

                        archivo_zip.write(ruta, relativa.as_posix())
                        cantidad += 1
                        total_bytes += ruta.stat().st_size

        archivo_temporal.seek(0)
    except Exception:
        archivo_temporal.close()
        raise

    return archivo_temporal, cantidad, total_bytes


class RespaldoAdjuntosView(SoloSuperusuarioMixin, AuditoriaMixin, View):
    """Descarga un ZIP con los adjuntos almacenados bajo MEDIA_ROOT."""

    accion = 'descargar'
    modelo = 'RespaldoAdjuntos'

    def get(self, request):
        archivo_temporal, cantidad, total_bytes = generar_zip_adjuntos(
            settings.MEDIA_ROOT
        )

        fecha = timezone.localtime().strftime('%Y%m%d_%H%M%S')
        nombre = f'respaldo_adjuntos_{fecha}.zip'

        try:
            self.registrar_acceso(
                request,
                detalle=(
                    f'Respaldo de adjuntos descargado: {cantidad} archivos, '
                    f'{total_bytes} bytes.'
                ),
            )
        except Exception:
            archivo_temporal.close()
            raise

        response = FileResponse(
            archivo_temporal,
            content_type='application/zip',
            as_attachment=True,
            filename=nombre,
        )
        response['X-Content-Type-Options'] = 'nosniff'
        return response

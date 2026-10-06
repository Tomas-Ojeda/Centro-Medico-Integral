from django.views.generic import CreateView, UpdateView, DeleteView
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.http import FileResponse, Http404
from django.conf import settings
import os
import mimetypes
from pathlib import Path
from pacientes.models import Paciente
from .models import Consulta
from .forms import ConsultaForm
from auditoria.mixins import AuditoriaMixin


class ConsultaCreateView(LoginRequiredMixin, AuditoriaMixin, CreateView):
    model = Consulta
    form_class = ConsultaForm
    template_name = 'historias/formulario.html'
    accion = 'crear'
    modelo = 'Consulta'

    def get_paciente(self):
        return get_object_or_404(Paciente, pk=self.kwargs['paciente_pk'])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['paciente'] = self.get_paciente()
        ctx['titulo'] = 'Nueva Consulta'
        return ctx

    def form_valid(self, form):
        form.instance.paciente = self.get_paciente()
        response = super().form_valid(form)
        self.registrar_acceso(self.request, form.instance)
        return response

    def get_success_url(self):
        return reverse('pacientes:detalle', kwargs={'pk': self.kwargs['paciente_pk']})


class ConsultaUpdateView(LoginRequiredMixin, AuditoriaMixin, UpdateView):
    model = Consulta
    form_class = ConsultaForm
    template_name = 'historias/formulario.html'
    accion = 'editar'
    modelo = 'Consulta'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['paciente'] = self.object.paciente
        ctx['titulo'] = 'Editar Consulta'
        return ctx

    def form_valid(self, form):
        response = super().form_valid(form)
        self.registrar_acceso(self.request, form.instance)
        return response

    def get_success_url(self):
        return reverse('pacientes:detalle', kwargs={'pk': self.object.paciente_id})


class ConsultaDeleteView(LoginRequiredMixin, AuditoriaMixin, DeleteView):
    model = Consulta
    template_name = 'historias/confirmar_eliminar.html'
    accion = 'borrar'
    modelo = 'Consulta'

    def get_success_url(self):
        return reverse('pacientes:detalle', kwargs={'pk': self.object.paciente_id})

    def delete(self, request, *args, **kwargs):
        objeto = self.get_object()
        response = super().delete(request, *args, **kwargs)
        self.registrar_acceso(request, objeto)
        return response


class DescargarArchivoAdjuntoView(LoginRequiredMixin, AuditoriaMixin, View):
    """Vista para servir archivos adjuntos de consultas de forma segura."""
    accion = 'descargar'
    modelo = 'Consulta'

    def get(self, request, consulta_pk):
        consulta = get_object_or_404(Consulta, pk=consulta_pk)
        self.registrar_acceso(request, consulta)

        if not consulta.archivo_adjunto:
            raise Http404("No hay archivo adjunto en esta consulta")

        archivo_path = consulta.archivo_adjunto.path

        # Validar que la ruta resuelta quede dentro de MEDIA_ROOT (path traversal)
        media_root = Path(settings.MEDIA_ROOT).resolve()
        ruta_resuelta = Path(archivo_path).resolve()
        if not str(ruta_resuelta).startswith(str(media_root)):
            raise Http404("Ruta de archivo inválida")

        if not os.path.exists(archivo_path):
            raise Http404("El archivo no existe en el servidor")

        # Determinar el tipo MIME
        content_type, _ = mimetypes.guess_type(archivo_path)
        if content_type is None:
            content_type = 'application/octet-stream'

        # Servir el archivo con headers de seguridad
        try:
            response = FileResponse(
                open(archivo_path, 'rb'),
                content_type=content_type,
                as_attachment=True,
                filename=os.path.basename(archivo_path)
            )
            # Prevenir que el navegador adivine el tipo MIME (XSS)
            response['X-Content-Type-Options'] = 'nosniff'
            return response
        except (IOError, OSError):
            raise Http404("Error al leer el archivo")

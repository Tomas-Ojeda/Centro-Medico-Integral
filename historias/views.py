from django.views.generic import CreateView, UpdateView, DeleteView
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.http import FileResponse, Http404
from django.conf import settings
import os
import mimetypes
from pacientes.models import Paciente
from .models import Consulta
from .forms import ConsultaForm


class ConsultaCreateView(LoginRequiredMixin, CreateView):
    model = Consulta
    form_class = ConsultaForm
    template_name = 'historias/formulario.html'

    def get_paciente(self):
        return get_object_or_404(Paciente, pk=self.kwargs['paciente_pk'])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['paciente'] = self.get_paciente()
        ctx['titulo'] = 'Nueva Consulta'
        return ctx

    def form_valid(self, form):
        form.instance.paciente = self.get_paciente()
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('pacientes:detalle', kwargs={'pk': self.kwargs['paciente_pk']})


class ConsultaUpdateView(LoginRequiredMixin, UpdateView):
    model = Consulta
    form_class = ConsultaForm
    template_name = 'historias/formulario.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['paciente'] = self.object.paciente
        ctx['titulo'] = 'Editar Consulta'
        return ctx

    def get_success_url(self):
        return reverse('pacientes:detalle', kwargs={'pk': self.object.paciente_id})


class ConsultaDeleteView(LoginRequiredMixin, DeleteView):
    model = Consulta
    template_name = 'historias/confirmar_eliminar.html'

    def get_success_url(self):
        return reverse('pacientes:detalle', kwargs={'pk': self.object.paciente_id})


class DescargarArchivoAdjuntoView(LoginRequiredMixin, View):
    """Vista para servir archivos adjuntos de consultas de forma segura."""
    
    def get(self, request, consulta_pk):
        consulta = get_object_or_404(Consulta, pk=consulta_pk)
        
        if not consulta.archivo_adjunto:
            raise Http404("No hay archivo adjunto en esta consulta")
        
        archivo_path = consulta.archivo_adjunto.path
        
        if not os.path.exists(archivo_path):
            raise Http404("El archivo no existe en el servidor")
        
        # Determinar el tipo MIME
        content_type, _ = mimetypes.guess_type(archivo_path)
        if content_type is None:
            content_type = 'application/octet-stream'
        
        # Servir el archivo
        try:
            response = FileResponse(
                open(archivo_path, 'rb'),
                content_type=content_type,
                as_attachment=True,
                filename=os.path.basename(archivo_path)
            )
            return response
        except (IOError, OSError):
            raise Http404("Error al leer el archivo")

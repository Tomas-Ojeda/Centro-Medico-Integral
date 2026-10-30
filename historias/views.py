from django.views.generic import CreateView, UpdateView, DeleteView
from django.views import View
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.http import FileResponse, Http404, JsonResponse
from django.conf import settings
from django.utils import timezone
import os
import mimetypes
from pathlib import Path
from pacientes.models import Paciente
from .models import (
    AdjuntoHistoria,
    CampoAdicional,
    Consulta,
    NotaClinica,
    validar_archivo_adjunto,
)
from .forms import ConsultaForm, NotaClinicaForm
from .permisos import (
    puede_crear_notas,
    puede_editar_nota,
)
from auditoria.mixins import AuditoriaMixin
from consultorio_salto.permisos import (
    RecepcionOProfesionalMixin,
    SoloRecepcionMixin,
    es_admin,
    es_profesional,
    profesional_actual,
)


class ConsultaCreateView(RecepcionOProfesionalMixin, LoginRequiredMixin, AuditoriaMixin, CreateView):
    model = Consulta
    form_class = ConsultaForm
    template_name = 'historias/formulario.html'
    accion = 'crear'
    modelo = 'Consulta'

    def get_paciente(self):
        if self.profesional:
            return get_object_or_404(
                Paciente.objects.atendidos_por(self.profesional),
                pk=self.kwargs['paciente_pk'],
            )
        return get_object_or_404(Paciente, pk=self.kwargs['paciente_pk'])

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['profesional_fijo'] = self.profesional
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        # Recepción puede preseleccionar un profesional con ?profesional=,
        # para que el formulario ofrezca también sus campos adicionales.
        if not self.profesional:
            profesional_id = self.request.GET.get('profesional')
            if profesional_id:
                initial['profesional'] = profesional_id
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['paciente'] = self.get_paciente()
        ctx['titulo'] = 'Nueva Consulta'
        return ctx

    def form_valid(self, form):
        form.instance.paciente = self.get_paciente()
        if self.profesional:
            form.instance.profesional = self.profesional
        response = super().form_valid(form)
        self.registrar_acceso(self.request, form.instance)
        return response

    def get_success_url(self):
        return reverse('pacientes:detalle', kwargs={'pk': self.kwargs['paciente_pk']})


class ConsultaUpdateView(RecepcionOProfesionalMixin, LoginRequiredMixin, AuditoriaMixin, UpdateView):
    model = Consulta
    form_class = ConsultaForm
    template_name = 'historias/formulario.html'
    accion = 'editar'
    modelo = 'Consulta'

    def get_queryset(self):
        qs = Consulta.objects.all()
        if self.profesional:
            qs = qs.filter(profesional=self.profesional)
        return qs

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['profesional_fijo'] = self.profesional
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['paciente'] = self.object.paciente
        ctx['titulo'] = 'Editar Consulta'
        return ctx

    def form_valid(self, form):
        if self.profesional:
            form.instance.profesional = self.profesional
        response = super().form_valid(form)
        self.registrar_acceso(self.request, form.instance)
        return response

    def get_success_url(self):
        return reverse('pacientes:detalle', kwargs={'pk': self.object.paciente_id})


class ConsultaDeleteView(SoloRecepcionMixin, LoginRequiredMixin, AuditoriaMixin, DeleteView):
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


class DescargarArchivoAdjuntoView(RecepcionOProfesionalMixin, LoginRequiredMixin, AuditoriaMixin, View):
    """Vista para servir archivos adjuntos de consultas de forma segura."""
    accion = 'descargar'
    modelo = 'Consulta'

    def get(self, request, consulta_pk):
        consulta = get_object_or_404(
            Consulta.objects.select_related('paciente'),
            pk=consulta_pk,
        )
        if self.profesional:
            paciente_habilitado = Paciente.objects.atendidos_por(
                self.profesional
            ).filter(pk=consulta.paciente_id).exists()
            if not paciente_habilitado:
                raise Http404('No tenés acceso a esta consulta')
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


class SubirAdjuntoHistoriaView(RecepcionOProfesionalMixin, LoginRequiredMixin, AuditoriaMixin, View):
    """Sube un archivo a la historia clínica del paciente."""

    accion = 'crear'
    modelo = 'AdjuntoHistoria'

    def get_paciente(self):
        if self.profesional:
            return get_object_or_404(
                Paciente.objects.atendidos_por(self.profesional),
                pk=self.kwargs['paciente_pk'],
            )
        return get_object_or_404(Paciente, pk=self.kwargs['paciente_pk'])

    def post(self, request, paciente_pk):
        paciente = self.get_paciente()
        archivo = request.FILES.get('archivo')

        if archivo is None:
            messages.error(request, 'Seleccioná un archivo para adjuntar.')
            return redirect('pacientes:detalle', pk=paciente.pk)

        try:
            validar_archivo_adjunto(archivo)
            with transaction.atomic():
                adjunto = AdjuntoHistoria.objects.create(
                    paciente=paciente,
                    archivo=archivo,
                    descripcion=request.POST.get('descripcion', '').strip()[:255],
                    subido_por=request.user,
                )
                self.registrar_acceso(request, adjunto)
        except ValidationError as exc:
            messages.error(request, ' '.join(exc.messages))
            return redirect('pacientes:detalle', pk=paciente.pk)

        messages.success(request, 'Adjunto agregado a la historia clínica.')
        return redirect('pacientes:detalle', pk=paciente.pk)


class EliminarAdjuntoHistoriaView(SoloRecepcionMixin, LoginRequiredMixin, AuditoriaMixin, View):
    """Elimina un adjunto de historia clínica y su archivo del storage."""

    accion = 'borrar'
    modelo = 'AdjuntoHistoria'

    def post(self, request, pk):
        adjunto = get_object_or_404(
            AdjuntoHistoria.objects.select_related('paciente'),
            pk=pk,
        )
        paciente_id = adjunto.paciente_id
        self.registrar_acceso(request, adjunto)
        adjunto.delete()
        messages.success(request, 'Adjunto eliminado.')
        return redirect('pacientes:detalle', pk=paciente_id)


class DescargarAdjuntoHistoriaView(RecepcionOProfesionalMixin, LoginRequiredMixin, AuditoriaMixin, View):
    """Sirve un adjunto de historia clínica según el rol del usuario.

    Usa ``archivo.open('rb')`` para no depender de ``.path`` y permitir
    storages remotos en el futuro.
    """

    accion = 'descargar'
    modelo = 'AdjuntoHistoria'

    def get(self, request, pk):
        adjuntos = AdjuntoHistoria.objects.select_related('paciente')
        if self.profesional:
            adjuntos = adjuntos.filter(
                paciente__in=Paciente.objects.atendidos_por(self.profesional)
            )
        adjunto = get_object_or_404(adjuntos, pk=pk)

        if not adjunto.archivo:
            raise Http404('El adjunto no tiene archivo.')

        content_type, _ = mimetypes.guess_type(adjunto.archivo.name)
        if content_type is None:
            content_type = 'application/octet-stream'

        try:
            archivo = adjunto.archivo.open('rb')
        except (FileNotFoundError, OSError):
            raise Http404('El archivo no existe en el servidor.')

        self.registrar_acceso(request, adjunto)
        response = FileResponse(
            archivo,
            content_type=content_type,
            as_attachment=not adjunto.es_imagen,
            filename=adjunto.nombre_archivo,
        )
        # Evita que el navegador adivine el tipo MIME (XSS).
        response['X-Content-Type-Options'] = 'nosniff'
        return response


class QuitarCampoAdicionalView(RecepcionOProfesionalMixin, LoginRequiredMixin, AuditoriaMixin, View):
    """Soft-delete de un campo adicional.

    El Admin puede quitar cualquier campo (incluidos los generales). Un
    profesional solo puede quitar los campos de los que es dueño. Los
    valores ya cargados en consultas se conservan.
    """

    accion = 'borrar'
    modelo = 'CampoAdicional'

    def post(self, request, pk):
        campo = get_object_or_404(CampoAdicional, pk=pk)

        if not es_admin(request.user):
            if (
                self.profesional is None
                or campo.profesional_id != self.profesional.pk
            ):
                return JsonResponse(
                    {'error': 'No tenés permiso para quitar este campo.'},
                    status=403,
                )

        if campo.activo:
            campo.activo = False
            campo.save(update_fields=['activo'])
            self.registrar_acceso(request, campo)

        return JsonResponse({'ok': True, 'pk': campo.pk})


class NotaClinicaCreateView(LoginRequiredMixin, AuditoriaMixin, View):
    """Agrega una anotación clínica a un paciente."""

    accion = 'crear'
    modelo = 'NotaClinica'

    def post(self, request, paciente_pk):
        if not puede_crear_notas(request.user):
            raise PermissionDenied(
                'No tenés permiso para agregar anotaciones.'
            )

        if es_admin(request.user):
            paciente = get_object_or_404(Paciente, pk=paciente_pk)
        else:
            profesional = profesional_actual(request.user)
            if profesional is None:
                raise PermissionDenied(
                    'Tu usuario no está vinculado a un profesional.'
                )
            paciente = get_object_or_404(
                Paciente.objects.atendidos_por(profesional),
                pk=paciente_pk,
            )

        form = NotaClinicaForm(request.POST)
        if not form.is_valid():
            messages.error(
                request,
                'La anotación no puede estar vacía ni superar los 10.000 caracteres.',
            )
            return redirect('pacientes:detalle', pk=paciente.pk)

        nota = form.save(commit=False)
        nota.paciente = paciente
        nota.autor = request.user
        nota.save()
        self.registrar_acceso(request, nota)
        messages.success(request, 'Anotación agregada.')
        return redirect('pacientes:detalle', pk=paciente.pk)


class NotaClinicaUpdateView(LoginRequiredMixin, AuditoriaMixin, View):
    """Edita una anotación. Solo el autor o el Admin."""

    accion = 'editar'
    modelo = 'NotaClinica'

    def post(self, request, pk):
        nota = get_object_or_404(
            NotaClinica.objects.select_related('paciente'),
            pk=pk,
        )

        if not puede_editar_nota(request.user, nota):
            raise PermissionDenied(
                'Solo el autor de la anotación puede editarla.'
            )

        if es_profesional(request.user):
            profesional = profesional_actual(request.user)
            if (
                profesional is None
                or not Paciente.objects.atendidos_por(profesional)
                .filter(pk=nota.paciente_id)
                .exists()
            ):
                raise Http404('No tenés acceso a este paciente.')

        form = NotaClinicaForm(request.POST, instance=nota)
        if not form.is_valid():
            messages.error(
                request,
                'La anotación no puede estar vacía ni superar los 10.000 caracteres.',
            )
            return redirect('pacientes:detalle', pk=nota.paciente_id)

        nota = form.save(commit=False)
        nota.editado_en = timezone.now()
        nota.save()
        self.registrar_acceso(request, nota)
        messages.success(request, 'Anotación actualizada.')
        return redirect('pacientes:detalle', pk=nota.paciente_id)


class NotaClinicaDeleteView(LoginRequiredMixin, AuditoriaMixin, View):
    """Elimina una anotación. Solo el Admin."""

    accion = 'borrar'
    modelo = 'NotaClinica'

    def post(self, request, pk):
        if not es_admin(request.user):
            raise PermissionDenied(
                'Solo el administrador puede eliminar anotaciones.'
            )

        nota = get_object_or_404(
            NotaClinica.objects.select_related('paciente'),
            pk=pk,
        )
        paciente_id = nota.paciente_id
        self.registrar_acceso(request, nota)
        nota.delete()
        messages.success(request, 'Anotación eliminada.')
        return redirect('pacientes:detalle', pk=paciente_id)

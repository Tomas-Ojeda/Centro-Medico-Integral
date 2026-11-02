from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, ListView

from auditoria.mixins import AuditoriaMixin
from consultorio_salto.permisos import (
    RecepcionOProfesionalMixin,
    es_admin,
)
from pacientes.models import Paciente
from profesionales.models import Profesional
from turnos.models import EstadoSolicitud

from .forms import DerivacionForm
from .models import Derivacion, EstadoDerivacion


class DerivacionListView(
    RecepcionOProfesionalMixin,
    LoginRequiredMixin,
    ListView,
):
    """Bandeja de derivaciones recibidas y enviadas."""

    model = Derivacion
    template_name = 'derivaciones/lista.html'
    context_object_name = 'derivaciones'

    def get_tab(self):
        tab = self.request.GET.get('tab', 'recibidas')
        if tab not in ('recibidas', 'enviadas'):
            return 'recibidas'
        return tab

    def get_queryset(self):
        qs = Derivacion.objects.select_related(
            'paciente',
            'profesional_origen',
            'profesional_destino',
            'solicitud_turno',
            'creado_por',
        )
        if self.profesional:
            if self.get_tab() == 'enviadas':
                qs = qs.filter(profesional_origen=self.profesional)
            else:
                qs = qs.filter(profesional_destino=self.profesional)
        return qs.order_by('-creado')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['tab'] = self.get_tab() if self.profesional else 'todas'

        if self.profesional:
            resumen = Derivacion.objects.filter(
                Q(profesional_destino=self.profesional)
                | Q(profesional_origen=self.profesional)
            ).aggregate(
                recibidas=Count(
                    'pk',
                    filter=Q(profesional_destino=self.profesional),
                ),
                enviadas=Count(
                    'pk',
                    filter=Q(profesional_origen=self.profesional),
                ),
                pendientes=Count(
                    'pk',
                    filter=Q(
                        profesional_destino=self.profesional,
                        estado=EstadoDerivacion.PENDIENTE,
                    ),
                ),
            )
            ctx.update(resumen)

        return ctx


class DerivacionCreateView(
    RecepcionOProfesionalMixin,
    LoginRequiredMixin,
    AuditoriaMixin,
    View,
):
    """Deriva un paciente a otro profesional y pide el turno."""

    template_name = 'derivaciones/formulario.html'
    accion = 'crear'
    modelo = 'Derivacion'

    def get_origen(self):
        """El profesional logueado; ``None`` si es Admin (lo elige)."""
        if es_admin(self.request.user):
            return None
        if self.profesional is None:
            raise PermissionDenied(
                'Solo los profesionales que atienden al paciente pueden '
                'derivarlo.'
            )
        return self.profesional

    def get_paciente(self):
        origen = self.get_origen()
        if origen is not None:
            return get_object_or_404(
                Paciente.objects.atendidos_por(origen),
                pk=self.kwargs['paciente_pk'],
            )
        return get_object_or_404(Paciente, pk=self.kwargs['paciente_pk'])

    def profesionales_origen(self, paciente):
        """Profesionales habilitados para derivar (solo para el Admin)."""
        return Profesional.objects.filter(
            Q(turnos__paciente=paciente)
            | Q(consultas__paciente=paciente)
            | Q(
                derivaciones_recibidas__paciente=paciente,
                derivaciones_recibidas__estado__in=[
                    EstadoDerivacion.PENDIENTE,
                    EstadoDerivacion.VISTA,
                ],
            )
        ).distinct().order_by('apellido', 'nombre')

    def construir_form(self, paciente, origen, data=None):
        permitir_origen = es_admin(self.request.user)
        kwargs = {
            'paciente': paciente,
            'profesional_origen': origen,
            'permitir_origen': permitir_origen,
        }
        if permitir_origen:
            kwargs['profesionales_origen'] = self.profesionales_origen(
                paciente
            )
        if data is not None:
            kwargs['data'] = data
        return DerivacionForm(**kwargs)

    def contexto(self, paciente, form, origen):
        destino_inicial = None
        valor = form['profesional_destino'].value()
        if valor:
            destino_inicial = Profesional.objects.filter(pk=valor).first()

        return {
            'paciente': paciente,
            'form': form,
            'profesional_origen': origen,
            'es_admin_form': es_admin(self.request.user),
            'profesional_destino_inicial': destino_inicial,
            'titulo': 'Derivar paciente',
        }

    def get(self, request, paciente_pk):
        paciente = self.get_paciente()
        origen = self.get_origen()
        form = self.construir_form(paciente, origen)
        return render(
            request,
            self.template_name,
            self.contexto(paciente, form, origen),
        )

    def post(self, request, paciente_pk):
        paciente = self.get_paciente()
        origen = self.get_origen()
        form = self.construir_form(paciente, origen, data=request.POST)

        if not form.is_valid():
            return render(
                request,
                self.template_name,
                self.contexto(paciente, form, origen),
            )

        with transaction.atomic():
            derivacion = form.save(commit=False)
            derivacion.creado_por = request.user
            derivacion.estado = EstadoDerivacion.PENDIENTE
            derivacion.save()
            derivacion.crear_solicitud_turno()

            self.registrar_acceso(
                request,
                derivacion,
                accion='crear',
                detalle=(
                    f'Derivación de {paciente} a '
                    f'{derivacion.profesional_destino}.'
                ),
            )

        messages.success(
            request,
            'Derivación creada. Recepción agendará el turno con el '
            'profesional de destino.',
        )
        if not derivacion.profesional_destino.usuario_id:
            messages.warning(
                request,
                'El profesional de destino no tiene usuario vinculado: '
                'no recibirá la notificación en la app.',
            )

        return redirect('derivaciones:detalle', pk=derivacion.pk)


class DerivacionDetailView(
    RecepcionOProfesionalMixin,
    LoginRequiredMixin,
    AuditoriaMixin,
    DetailView,
):
    """Detalle de una derivación. Al abrirla el destino la marca vista."""

    model = Derivacion
    template_name = 'derivaciones/detalle.html'
    context_object_name = 'derivacion'
    accion = 'ver'
    modelo = 'Derivacion'

    def get_queryset(self):
        qs = Derivacion.objects.select_related(
            'paciente',
            'profesional_origen',
            'profesional_destino',
            'solicitud_turno',
            'creado_por',
        )
        if self.profesional:
            qs = qs.filter(
                Q(profesional_origen=self.profesional)
                | Q(profesional_destino=self.profesional)
            )
        return qs

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()

        es_destino = bool(
            self.profesional
            and self.object.profesional_destino_id == self.profesional.pk
        )
        if es_destino and self.object.estado == EstadoDerivacion.PENDIENTE:
            with transaction.atomic():
                self.object.estado = EstadoDerivacion.VISTA
                self.object.vista_en = timezone.now()
                self.object.save(update_fields=['estado', 'vista_en'])
                self.registrar_acceso(
                    request,
                    self.object,
                    accion='ver',
                    detalle='Derivación marcada como vista.',
                )
        else:
            self.registrar_acceso(
                request,
                self.object,
                accion='ver',
                detalle='Consulta de derivación.',
            )

        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['es_destino'] = bool(
            self.profesional
            and self.object.profesional_destino_id == self.profesional.pk
        )
        ctx['puede_cancelar'] = (
            self.object.estado == EstadoDerivacion.PENDIENTE
            and (
                es_admin(self.request.user)
                or bool(
                    self.profesional
                    and self.object.profesional_origen_id
                    == self.profesional.pk
                )
            )
        )
        return ctx


class DerivacionCancelView(
    RecepcionOProfesionalMixin,
    LoginRequiredMixin,
    AuditoriaMixin,
    View,
):
    """El profesional de origen cancela una derivación pendiente."""

    accion = 'editar'
    modelo = 'Derivacion'

    def post(self, request, pk):
        derivacion = get_object_or_404(
            Derivacion.objects.select_related(
                'paciente',
                'profesional_origen',
                'profesional_destino',
                'solicitud_turno',
            ),
            pk=pk,
        )

        permitido = es_admin(request.user) or bool(
            self.profesional
            and derivacion.profesional_origen_id == self.profesional.pk
        )
        if not permitido:
            raise PermissionDenied(
                'Solo el profesional de origen puede cancelar la derivación.'
            )

        if derivacion.estado != EstadoDerivacion.PENDIENTE:
            messages.warning(
                request,
                'La derivación ya no está pendiente y no se puede cancelar.',
            )
            return redirect('derivaciones:detalle', pk=derivacion.pk)

        with transaction.atomic():
            derivacion.estado = EstadoDerivacion.CANCELADA
            derivacion.save(update_fields=['estado'])

            solicitud = derivacion.solicitud_turno
            if (
                solicitud is not None
                and solicitud.estado == EstadoSolicitud.PENDIENTE
            ):
                solicitud.estado = EstadoSolicitud.DESCARTADA
                solicitud.resuelto_en = timezone.now()
                solicitud.resuelto_por = request.user
                solicitud.motivo_resolucion = 'Derivación cancelada.'
                solicitud.save(update_fields=[
                    'estado',
                    'resuelto_en',
                    'resuelto_por',
                    'motivo_resolucion',
                ])
                self.registrar_acceso(
                    request,
                    solicitud,
                    accion='editar',
                    detalle='Solicitud descartada por cancelación de derivación.',
                    modelo='SolicitudTurno',
                )

            self.registrar_acceso(
                request,
                derivacion,
                accion='editar',
                detalle=(
                    f'Derivación cancelada por '
                    f'{derivacion.profesional_origen}.'
                ),
            )

        messages.success(request, 'Derivación cancelada.')
        return redirect('derivaciones:detalle', pk=derivacion.pk)


class DerivacionDeleteView(
    LoginRequiredMixin,
    AuditoriaMixin,
    View,
):
    """Elimina definitivamente una derivación. Solo para administradores.

    Si la derivación tenía una solicitud de turno pendiente y no está
    compartida con otra derivación, la solicitud se descarta para que no quede
    en la cola de "Turnos por agendar".
    """

    accion = 'borrar'
    modelo = 'Derivacion'

    def post(self, request, pk):
        if not es_admin(request.user):
            raise PermissionDenied(
                'Solo el administrador puede eliminar derivaciones.'
            )

        derivacion = get_object_or_404(
            Derivacion.objects.select_related(
                'paciente',
                'profesional_origen',
                'profesional_destino',
                'solicitud_turno',
            ),
            pk=pk,
        )
        solicitud = derivacion.solicitud_turno

        with transaction.atomic():
            self.registrar_acceso(
                request,
                derivacion,
                accion='borrar',
                detalle=(
                    f'Derivación de {derivacion.paciente} eliminada por '
                    f'{request.user.username}.'
                ),
            )
            derivacion.delete()

            if (
                solicitud is not None
                and solicitud.estado == EstadoSolicitud.PENDIENTE
                and not Derivacion.objects.filter(
                    solicitud_turno=solicitud
                ).exists()
            ):
                solicitud.estado = EstadoSolicitud.DESCARTADA
                solicitud.resuelto_en = timezone.now()
                solicitud.resuelto_por = request.user
                solicitud.motivo_resolucion = 'Derivación eliminada.'
                solicitud.save(update_fields=[
                    'estado',
                    'resuelto_en',
                    'resuelto_por',
                    'motivo_resolucion',
                ])
                self.registrar_acceso(
                    request,
                    solicitud,
                    accion='editar',
                    detalle=(
                        'Solicitud descartada por eliminación de derivación.'
                    ),
                    modelo='SolicitudTurno',
                )

        messages.success(request, 'Derivación eliminada.')
        return redirect('derivaciones:lista')


class BuscarProfesionalesDerivacionView(
    RecepcionOProfesionalMixin,
    LoginRequiredMixin,
    View,
):
    """Endpoint JSON con los profesionales activos para derivar."""

    def get(self, request):
        q = request.GET.get('q', '').strip()
        profesionales = Profesional.objects.filter(activo=True)

        if self.profesional:
            profesionales = profesionales.exclude(pk=self.profesional.pk)

        if q:
            profesionales = profesionales.filter(
                Q(nombre__icontains=q)
                | Q(apellido__icontains=q)
                | Q(especialidades__nombre__icontains=q)
            )

        profesionales = profesionales.prefetch_related(
            'especialidades'
        ).distinct().order_by('apellido', 'nombre')[:20]

        data = [{
            'id': profesional.pk,
            'nombre': profesional.nombre,
            'apellido': profesional.apellido,
            'nombre_completo': f'{profesional.apellido}, {profesional.nombre}',
            'especialidad': ', '.join(
                e.nombre for e in profesional.especialidades.all()
            ),
            'tiene_usuario': bool(profesional.usuario_id),
        } for profesional in profesionales]

        return JsonResponse({'results': data})

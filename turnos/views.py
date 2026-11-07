from django.conf import settings
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse, reverse_lazy
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.db import transaction
from django.db.models import (
    Case,
    Count,
    DateTimeField,
    F,
    IntegerField,
    Q,
    Value,
    When,
)
from django.http import HttpResponse, JsonResponse
from datetime import datetime, time, timedelta
from urllib.parse import urlencode
import csv
from .models import (
    ESTADOS_EN_SALA,
    EstadoSolicitud,
    EstadoTurno,
    MotivoSalida,
    SolicitudTurno,
    Turno,
    filtro_en_sala_espera,
)
from .forms import (
    DescartarSolicitudForm,
    PagoTurnoForm,
    SolicitudTurnoForm,
    TurnoForm,
)
from .utils import fecha_desde_request, rango_del_dia, texto_pago
from historias.models import AdjuntoHistoria
from profesionales.models import Profesional
from pacientes.models import Paciente
from auditoria.mixins import AuditoriaMixin
from consultorio_salto.permisos import (
    RecepcionOProfesionalMixin,
    SoloRecepcionMixin,
    es_recepcion,
)


CAMPOS_FILTRO_AGENDA = ('especialidad', 'profesional', 'q', 'orden', 'vista')


def puede_llamar_paciente(user, turno, profesional):
    """Permiso para marcar que el paciente pasó a consultorio.

    Recepción/Admin siempre pueden. El profesional solo respecto de sus
    propios turnos y cuando el setting lo habilita.
    """
    if es_recepcion(user):
        return True
    return bool(
        profesional
        and settings.PROFESIONAL_PUEDE_LLAMAR_PACIENTE
        and turno.profesional_id == profesional.pk
    )


def aplicar_filtros_agenda(queryset, request, profesional):
    """Aplica los filtros visibles de la agenda a un queryset de turnos."""
    if profesional:
        queryset = queryset.filter(profesional=profesional)

    especialidad = request.GET.get('especialidad', '')
    profesional_id = request.GET.get('profesional', '')
    q = request.GET.get('q', '').strip()

    if especialidad:
        queryset = queryset.filter(
            profesional__especialidades__nombre__iexact=especialidad
        ).distinct()
    if profesional_id:
        queryset = queryset.filter(profesional_id=profesional_id)
    if q:
        queryset = queryset.filter(
            Q(paciente__nombre__icontains=q) |
            Q(paciente__apellido__icontains=q) |
            Q(paciente__dni__icontains=q)
        )
    return queryset


def ordenar_turnos(queryset, orden):
    """Orden de la agenda; con ``llegada`` la sala de espera va primero."""
    if orden != 'llegada':
        return queryset.order_by('fecha_hora')

    en_sala = filtro_en_sala_espera()
    return queryset.annotate(
        _prioridad_sala=Case(
            When(en_sala, then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        ),
        _orden_llegada=Case(
            When(en_sala, then=F('hora_llegada')),
            default=Value(None),
            output_field=DateTimeField(),
        ),
    ).order_by(
        '_prioridad_sala',
        F('_orden_llegada').asc(nulls_last=True),
        'fecha_hora',
    )


def url_de_retorno(request, por_defecto):
    """Devuelve ``next`` solo si es un destino local y seguro."""
    destino = request.POST.get('next') or request.GET.get('next')
    if destino and url_has_allowed_host_and_scheme(
        destino,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return destino
    return por_defecto


def agenda_con_filtros(request, fecha):
    """URL de la agenda conservando fecha y filtros del POST/GET."""
    params = {'fecha': fecha.isoformat()}
    for campo in CAMPOS_FILTRO_AGENDA:
        valor = request.POST.get(campo) or request.GET.get(campo)
        if valor:
            params[campo] = valor
    return f"{reverse('turnos:agenda')}?{urlencode(params)}"


def construir_grupos_sala(turnos):
    """Agrupa la cola por profesional, ordenada por hora de llegada."""
    grupos = []
    por_profesional = {}
    for turno in turnos:
        clave = turno.profesional_id
        grupo = por_profesional.get(clave)
        if grupo is None:
            grupo = {
                'profesional': turno.profesional,
                'cola': [],
            }
            por_profesional[clave] = grupo
            grupos.append(grupo)
        grupo['cola'].append(turno)
    return grupos


class TurnoAgendaView(RecepcionOProfesionalMixin, LoginRequiredMixin, ListView):
    model = Turno
    template_name = 'turnos/agenda.html'
    context_object_name = 'turnos'

    def get_queryset(self):
        qs = Turno.objects.select_related(
            'paciente', 'profesional', 'pago_registrado_por',
            'llegada_marcada_por',
        ).prefetch_related('profesional__especialidades').annotate(
            num_adjuntos=Count('adjuntos_historia', distinct=True)
        )

        self.fecha_seleccionada = fecha_desde_request(self.request)
        inicio, fin = rango_del_dia(self.fecha_seleccionada)
        qs = qs.filter(fecha_hora__gte=inicio, fecha_hora__lt=fin)
        qs = aplicar_filtros_agenda(qs, self.request, self.profesional)

        self.orden = self.request.GET.get('orden', 'hora')
        if self.orden not in ('hora', 'llegada'):
            self.orden = 'hora'
        return ordenar_turnos(qs, self.orden)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        hoy = timezone.localdate()
        ctx['vista'] = self.request.GET.get('vista', 'lista')
        ctx['fecha_seleccionada'] = self.fecha_seleccionada
        ctx['hoy'] = hoy
        ctx['es_hoy'] = self.fecha_seleccionada == hoy
        ctx['orden'] = self.orden
        ctx['fecha_str'] = self.fecha_seleccionada.strftime('%Y-%m-%d')
        ctx['fecha_anterior'] = (self.fecha_seleccionada - timedelta(days=1)).strftime('%Y-%m-%d')
        ctx['fecha_siguiente'] = (self.fecha_seleccionada + timedelta(days=1)).strftime('%Y-%m-%d')
        from profesionales.models import Especialidad
        if self.profesional:
            ctx['especialidades'] = self.profesional.especialidades.values_list(
                'nombre', flat=True
            )
            ctx['profesionales'] = [self.profesional]
        else:
            ctx['especialidades'] = Especialidad.objects.values_list('nombre', flat=True).distinct()
            ctx['profesionales'] = Profesional.objects.filter(activo=True)
        ctx['filtro_especialidad'] = self.request.GET.get('especialidad', '')
        ctx['filtro_profesional'] = self.request.GET.get('profesional', '')
        ctx['q'] = self.request.GET.get('q', '')
        turnos_agenda = list(ctx['turnos'])
        ctx['turnos'] = turnos_agenda
        ctx['total_dia'] = len(turnos_agenda)

        puede_sacar = es_recepcion(self.request.user)
        for turno in turnos_agenda:
            turno.puede_llamar = puede_llamar_paciente(
                self.request.user,
                turno,
                self.profesional,
            )
            turno.puede_sacar = puede_sacar
            turno.puede_volver = bool(
                puede_sacar
                or (
                    self.profesional
                    and turno.profesional_id == self.profesional.pk
                )
            )

        inicio, fin = rango_del_dia(self.fecha_seleccionada)
        todos_dia = Turno.objects.filter(
            fecha_hora__gte=inicio,
            fecha_hora__lt=fin,
        )
        if self.profesional:
            todos_dia = todos_dia.filter(profesional=self.profesional)
        ctx['stats_dia'] = {
            'pendientes': todos_dia.filter(estado='pendiente').count(),
            'confirmados': todos_dia.filter(estado='confirmado').count(),
            'realizados': todos_dia.filter(estado='realizado').count(),
            'ausentes': todos_dia.filter(estado='ausente').count(),
        }

        # Cola de sala de espera del día (respeta los filtros de la agenda).
        cola_sala = [turno for turno in turnos_agenda if turno.en_sala_espera]
        cola_sala.sort(key=lambda turno: turno.hora_llegada)
        grupos_sala = construir_grupos_sala(cola_sala)
        for grupo in grupos_sala:
            for posicion, turno in enumerate(grupo['cola'], start=1):
                turno.posicion_sala = posicion
                turno.resaltado_sala = posicion == 1
        ctx['grupos_sala'] = grupos_sala
        ctx['total_sala'] = len(cola_sala)
        ctx['sala_url'] = (
            f"{reverse('turnos:sala_espera')}?{self.request.GET.urlencode()}"
        )

        # Datos para el calendario mensual
        import calendar
        
        mes = self.fecha_seleccionada.month
        anio = self.fecha_seleccionada.year
        
        # Calcular mes anterior y siguiente
        if mes == 1:
            mes_anterior = 12
            anio_anterior = anio - 1
        else:
            mes_anterior = mes - 1
            anio_anterior = anio
        
        if mes == 12:
            mes_siguiente = 1
            anio_siguiente = anio + 1
        else:
            mes_siguiente = mes + 1
            anio_siguiente = anio
        
        # Nombres de meses en español
        meses_espanol = {
            1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
            5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
            9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
        }
        
        # Obtener el primer día del mes y el número de días
        # calendar.monthrange devuelve (primer_dia_semana, dias_en_mes)
        # donde primer_dia_semana: 0=lunes, 1=martes, ..., 6=domingo
        primer_dia_semana, dias_en_mes = calendar.monthrange(anio, mes)
        
        # Obtener todos los turnos del mes
        turnos_mes = Turno.objects.filter(
            fecha_hora__year=anio,
            fecha_hora__month=mes
        )
        if self.profesional:
            turnos_mes = turnos_mes.filter(profesional=self.profesional)
        turnos_mes = turnos_mes.select_related(
            'paciente', 'profesional'
        ).prefetch_related('profesional__especialidades').annotate(
            num_adjuntos=Count('adjuntos_historia', distinct=True)
        )
        
        # Crear diccionario de turnos por día
        turnos_por_dia = {}
        for turno in turnos_mes:
            dia = turno.fecha_hora.day
            if dia not in turnos_por_dia:
                turnos_por_dia[dia] = []
            turnos_por_dia[dia].append({
                'id': turno.pk,
                'hora': turno.fecha_hora.strftime('%H:%M'),
                'paciente': f'{turno.paciente.apellido}, {turno.paciente.nombre}',
                'estado': turno.estado,
                'especialidad': turno.especialidad_actual,
                'num_adjuntos': turno.num_adjuntos,
            })
        
        # Construir las semanas del calendario
        semanas = []
        semana_actual = []
        
        # Agregar días vacíos al principio
        for _ in range(primer_dia_semana):
            semana_actual.append(None)
        
        # Agregar los días del mes
        for dia in range(1, dias_en_mes + 1):
            semana_actual.append({
                'dia': dia,
                'es_hoy': (
                    dia == hoy.day
                    and mes == hoy.month
                    and anio == hoy.year
                ),
                'turnos': turnos_por_dia.get(dia, [])
            })
            if len(semana_actual) == 7:
                semanas.append(semana_actual)
                semana_actual = []
        
        # Agregar la última semana si no está completa
        if semana_actual:
            while len(semana_actual) < 7:
                semana_actual.append(None)
            semanas.append(semana_actual)
        
        ctx['calendario'] = {
            'semanas': semanas,
            'mes_nombre': meses_espanol[mes],
            'anio': anio,
            'mes': mes,
            'mes_anterior_str': f'{anio_anterior}-{mes_anterior:02d}-01',
            'mes_siguiente_str': f'{anio_siguiente}-{mes_siguiente:02d}-01',
        }
        
        return ctx


class SalaEsperaJSONView(
    RecepcionOProfesionalMixin,
    LoginRequiredMixin,
    View,
):
    """Cola de sala de espera para refrescar la agenda sin recargar."""

    def get(self, request):
        fecha = fecha_desde_request(request)
        inicio, fin = rango_del_dia(fecha)
        turnos = Turno.objects.filter(
            fecha_hora__gte=inicio,
            fecha_hora__lt=fin,
            hora_llegada__isnull=False,
        ).select_related(
            'paciente', 'profesional'
        )
        turnos = aplicar_filtros_agenda(turnos, request, self.profesional)
        turnos = turnos.order_by('hora_llegada')

        ahora = timezone.now()
        cola = []
        grupos = []
        por_profesional = {}
        llegadas = {}
        esperas = {}
        salidas = {}
        puede_sacar = es_recepcion(request.user)

        for turno in turnos:
            hora_llegada = timezone.localtime(turno.hora_llegada)
            hora_texto = hora_llegada.strftime('%H:%M')
            minutos = max(
                0,
                int((ahora - turno.hora_llegada).total_seconds() // 60),
            )
            llegadas[str(turno.pk)] = hora_texto
            esperas[str(turno.pk)] = minutos

            if turno.salio_de_sala:
                salidas[str(turno.pk)] = {
                    'hora': timezone.localtime(
                        turno.hora_salida
                    ).strftime('%H:%M'),
                    'motivo': turno.motivo_salida,
                }

            if not turno.en_sala_espera:
                continue

            item = {
                'id': turno.pk,
                'turno_id': turno.pk,
                'paciente': (
                    f'{turno.paciente.apellido}, {turno.paciente.nombre}'
                ),
                'hora_turno': timezone.localtime(
                    turno.fecha_hora
                ).strftime('%H:%M'),
                'hora_llegada': hora_texto,
                'espera_minutos': minutos,
                'profesional_id': turno.profesional_id,
                'profesional': (
                    f'{turno.profesional.apellido}, '
                    f'{turno.profesional.nombre}'
                ),
                'puede_llamar': puede_llamar_paciente(
                    request.user,
                    turno,
                    self.profesional,
                ),
                'puede_sacar': puede_sacar,
                'salida_url': reverse('turnos:salida', args=[turno.pk]),
            }
            cola.append(item)

            grupo = por_profesional.get(turno.profesional_id)
            if grupo is None:
                grupo = {
                    'profesional_id': turno.profesional_id,
                    'profesional': item['profesional'],
                    'turnos': [],
                }
                por_profesional[turno.profesional_id] = grupo
                grupos.append(grupo)
            grupo['turnos'].append(item)

        return JsonResponse({
            'fecha': fecha.isoformat(),
            'cola': cola,
            'turnos': cola,
            'grupos': grupos,
            'llegadas': llegadas,
            'esperas': esperas,
            'salidas': salidas,
            'total': len(cola),
        })


class BuscarPacientesView(SoloRecepcionMixin, LoginRequiredMixin, View):
    """Endpoint JSON para búsqueda de pacientes con autocompletado."""
    def get(self, request):
        q = request.GET.get('q', '').strip()
        if not q:
            # Si no hay query, devolver todos los pacientes (limitado)
            pacientes = Paciente.objects.filter(activo=True).order_by('apellido', 'nombre')[:50]
        else:
            pacientes = Paciente.objects.filter(
                Q(nombre__icontains=q) |
                Q(apellido__icontains=q) |
                Q(dni__icontains=q)
            ).filter(activo=True).order_by('apellido', 'nombre')[:20]
        
        data = [{
            'id': p.pk,
            'nombre': p.nombre,
            'apellido': p.apellido,
            'dni': p.dni,
            'nombre_completo': f'{p.apellido}, {p.nombre}',
            'obra_social': p.obra_social,
        } for p in pacientes]
        
        return JsonResponse({'results': data})


class BuscarProfesionalesView(SoloRecepcionMixin, LoginRequiredMixin, View):
    """Endpoint JSON para búsqueda de profesionales con autocompletado."""
    def get(self, request):
        q = request.GET.get('q', '').strip()
        if not q:
            # Si no hay query, devolver todos los profesionales activos
            profesionales = Profesional.objects.filter(activo=True).order_by('apellido', 'nombre')[:50]
        else:
            profesionales = Profesional.objects.filter(
                Q(nombre__icontains=q) |
                Q(apellido__icontains=q) |
                Q(especialidades__nombre__icontains=q)
            ).filter(activo=True).order_by('apellido', 'nombre')[:20]
        
        data = [{
            'id': p.pk,
            'nombre': p.nombre,
            'apellido': p.apellido,
            'dni': p.dni,
            'especialidad': ', '.join([e.nombre for e in p.especialidades.all()]),
            'nombre_completo': f'{p.apellido}, {p.nombre}',
        } for p in profesionales]
        
        return JsonResponse({'results': data})


class ExportarAgendaCSVView(SoloRecepcionMixin, LoginRequiredMixin, AuditoriaMixin, View):
    accion = 'exportar'
    modelo = 'Turno'

    def get(self, request):
        self.registrar_acceso(request)
        fecha = fecha_desde_request(request)
        inicio, fin = rango_del_dia(fecha)

        turnos = Turno.objects.filter(
            fecha_hora__gte=inicio,
            fecha_hora__lt=fin,
        ).select_related(
            'paciente', 'profesional', 'pago_registrado_por'
        ).prefetch_related(
            'profesional__especialidades'
        ).order_by('fecha_hora')

        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="agenda_{fecha.strftime("%Y%m%d")}.csv"'
        response.write('\ufeff')  # BOM para Excel

        writer = csv.writer(response)
        writer.writerow([
            'Hora', 'Paciente', 'DNI', 'Especialidad', 'Profesional',
            'Estado', 'Motivo', 'Observaciones', 'Forma de pago', 'Monto',
            'Fecha de pago', 'Pago registrado por',
        ])
        for t in turnos:
            fecha_pago = ''
            if t.fecha_pago:
                fecha_pago = timezone.localtime(t.fecha_pago).strftime(
                    '%d/%m/%Y %H:%M'
                )
            writer.writerow([
                t.fecha_hora.strftime('%H:%M'),
                f'{t.paciente.apellido}, {t.paciente.nombre}',
                t.paciente.dni,
                t.especialidad_actual,
                f'{t.profesional.apellido}, {t.profesional.nombre}',
                t.get_estado_display(),
                t.motivo,
                t.observaciones,
                t.get_forma_pago_display() if t.forma_pago else '',
                f'{t.monto:.2f}' if t.monto is not None else '',
                fecha_pago,
                t.pago_registrado_por.username if t.pago_registrado_por else '',
            ])

        return response


class TurnoCreateView(SoloRecepcionMixin, LoginRequiredMixin, AuditoriaMixin, CreateView):
    model = Turno
    form_class = TurnoForm
    template_name = 'turnos/formulario.html'
    success_url = reverse_lazy('turnos:agenda')
    accion = 'crear'
    modelo = 'Turno'

    def get_solicitud(self):
        """Solicitud de origen, si el turno se agenda desde la cola."""
        if not hasattr(self, '_solicitud'):
            solicitud_id = (
                self.request.POST.get('solicitud')
                or self.request.GET.get('solicitud')
            )
            self._solicitud = None
            if solicitud_id:
                self._solicitud = get_object_or_404(
                    SolicitudTurno.objects.select_related(
                        'paciente', 'profesional'
                    ),
                    pk=solicitud_id,
                )
        return self._solicitud

    def solicitud_pendiente(self):
        solicitud = self.get_solicitud()
        if solicitud and solicitud.estado == EstadoSolicitud.PENDIENTE:
            return solicitud
        return None

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Nuevo Turno'
        ctx['solicitud'] = self.solicitud_pendiente()

        form = ctx.get('form')
        paciente_id = form['paciente'].value() if form else None
        profesional_id = form['profesional'].value() if form else None
        ctx['paciente_inicial'] = (
            Paciente.objects.filter(pk=paciente_id).first()
            if paciente_id else None
        )
        ctx['profesional_inicial'] = (
            Profesional.objects.filter(pk=profesional_id).first()
            if profesional_id else None
        )
        return ctx

    def get_initial(self):
        initial = super().get_initial()
        solicitud = self.solicitud_pendiente()

        if solicitud:
            initial['paciente'] = solicitud.paciente_id
            initial['profesional'] = solicitud.profesional_id
            initial['fecha_hora'] = datetime.combine(
                solicitud.fecha_sugerida,
                time(9, 0),
            )
            return initial

        paciente_id = self.request.GET.get('paciente')
        if paciente_id:
            initial['paciente'] = paciente_id

        profesional_id = self.request.GET.get('profesional')
        if profesional_id:
            initial['profesional'] = profesional_id

        fecha_sugerida = self.request.GET.get('fecha_sugerida')
        if fecha_sugerida:
            try:
                fecha = datetime.strptime(
                    fecha_sugerida, '%Y-%m-%d'
                ).date()
            except ValueError:
                fecha = None
            if fecha:
                initial['fecha_hora'] = datetime.combine(fecha, time(9, 0))

        return initial

    def form_valid(self, form):
        solicitud = self.solicitud_pendiente()

        if solicitud and (
            solicitud.paciente_id != form.cleaned_data['paciente'].pk
            or solicitud.profesional_id != form.cleaned_data['profesional'].pk
        ):
            form.add_error(
                None,
                'La solicitud no corresponde al paciente y profesional '
                'seleccionados.',
            )
            return self.form_invalid(form)

        try:
            with transaction.atomic():
                self._solicitud_agendada = bool(solicitud)
                response = super().form_valid(form)
                for archivo in form.cleaned_data.get('adjuntos') or []:
                    AdjuntoHistoria.objects.create(
                        paciente=form.instance.paciente,
                        turno=form.instance,
                        archivo=archivo,
                        subido_por=self.request.user,
                    )
                self.registrar_acceso(self.request, form.instance)

                if solicitud:
                    solicitud.estado = EstadoSolicitud.AGENDADA
                    solicitud.turno = form.instance
                    solicitud.resuelto_en = timezone.now()
                    solicitud.resuelto_por = self.request.user
                    solicitud.save(update_fields=[
                        'estado',
                        'turno',
                        'resuelto_en',
                        'resuelto_por',
                    ])
                    self._solicitud_agendada = True
                    fecha = timezone.localtime(
                        form.instance.fecha_hora
                    ).strftime('%d/%m/%Y %H:%M')
                    self.registrar_acceso(
                        self.request,
                        solicitud,
                        accion='editar',
                        detalle=(
                            f'Turno #{form.instance.pk} agendado para el '
                            f'{fecha}.'
                        ),
                        modelo='SolicitudTurno',
                    )
        except ValidationError as exc:
            form.add_error('adjuntos', exc)
            return self.form_invalid(form)

        if solicitud:
            messages.success(
                self.request,
                'Turno agendado y solicitud cerrada.',
            )
        return response

    def get_success_url(self):
        if getattr(self, '_solicitud_agendada', False):
            return reverse('turnos:por_agendar')
        return reverse('turnos:agenda')


class TurnoUpdateView(SoloRecepcionMixin, LoginRequiredMixin, AuditoriaMixin, UpdateView):
    model = Turno
    form_class = TurnoForm
    template_name = 'turnos/formulario.html'
    success_url = reverse_lazy('turnos:agenda')
    accion = 'editar'
    modelo = 'Turno'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Editar Turno'
        ctx['paciente_inicial'] = self.object.paciente
        ctx['profesional_inicial'] = self.object.profesional
        ctx['adjuntos_turno'] = self.object.adjuntos_historia.select_related(
            'subido_por'
        ).order_by('-creado')
        return ctx

    def form_valid(self, form):
        try:
            with transaction.atomic():
                response = super().form_valid(form)
                for archivo in form.cleaned_data.get('adjuntos') or []:
                    AdjuntoHistoria.objects.create(
                        paciente=form.instance.paciente,
                        turno=form.instance,
                        archivo=archivo,
                        subido_por=self.request.user,
                    )
                self.registrar_acceso(self.request, form.instance)
        except ValidationError as exc:
            form.add_error('adjuntos', exc)
            return self.form_invalid(form)
        return response


class TurnoDeleteView(SoloRecepcionMixin, LoginRequiredMixin, AuditoriaMixin, DeleteView):
    model = Turno
    template_name = 'turnos/confirmar_eliminar.html'
    success_url = reverse_lazy('turnos:agenda')
    accion = 'borrar'
    modelo = 'Turno'

    def delete(self, request, *args, **kwargs):
        objeto = self.get_object()
        response = super().delete(request, *args, **kwargs)
        self.registrar_acceso(request, objeto)
        return response


class CambiarEstadoTurnoView(
    SoloRecepcionMixin,
    LoginRequiredMixin,
    AuditoriaMixin,
    View,
):
    accion = 'editar'
    modelo = 'Turno'

    def post(self, request, pk, estado):
        turno = get_object_or_404(
            Turno.objects.select_related('paciente', 'profesional'),
            pk=pk,
        )
        estados_validos = [e.value for e in EstadoTurno]
        if estado in estados_validos:
            anterior = turno.estado
            if anterior != estado:
                turno.estado = estado
                campos = ['estado', 'modificado']
                detalle = (
                    'Estado cambiado de '
                    f'{dict(EstadoTurno.choices).get(anterior, anterior)} '
                    f'a {dict(EstadoTurno.choices).get(estado, estado)}.'
                )

                # Al cerrar el turno ya no corresponde mostrar que el
                # paciente sigue en consultorio o en la sala de espera.
                if estado not in ESTADOS_EN_SALA:
                    habia_salida = bool(
                        turno.hora_salida
                        or turno.motivo_salida
                        or turno.salida_marcada_por_id
                    )
                    turno.hora_salida = None
                    turno.motivo_salida = ''
                    turno.salida_marcada_por = None
                    campos += [
                        'hora_salida',
                        'motivo_salida',
                        'salida_marcada_por',
                    ]
                    if habia_salida:
                        detalle += (
                            ' Se quitó la marca de la sala de espera.'
                        )

                turno.save(update_fields=campos)
                self.registrar_acceso(request, turno, detalle=detalle)
        else:
            messages.error(request, 'El estado indicado no es válido.')

        fecha = timezone.localtime(turno.fecha_hora).date()
        return redirect(
            url_de_retorno(request, agenda_con_filtros(request, fecha))
        )


class MarcarLlegadaView(
    SoloRecepcionMixin,
    LoginRequiredMixin,
    AuditoriaMixin,
    View,
):
    """Marca o deshace la llegada del paciente a la sala de espera."""

    accion = 'editar'
    modelo = 'Turno'

    def post(self, request, pk):
        turno = get_object_or_404(
            Turno.objects.select_related('paciente', 'profesional'),
            pk=pk,
        )
        fecha_turno = timezone.localtime(turno.fecha_hora).date()
        destino = agenda_con_filtros(request, fecha_turno)

        if fecha_turno != timezone.localdate():
            messages.error(
                request,
                'Solo se puede marcar la llegada el día del turno.',
            )
            return redirect(url_de_retorno(request, destino))

        if turno.estado not in ESTADOS_EN_SALA:
            messages.error(
                request,
                'Solo se puede marcar la llegada de turnos pendientes '
                'o confirmados.',
            )
            return redirect(url_de_retorno(request, destino))

        if turno.hora_llegada is None:
            turno.hora_llegada = timezone.now()
            turno.llegada_marcada_por = request.user
            turno.hora_salida = None
            turno.motivo_salida = ''
            turno.salida_marcada_por = None
            accion = (
                f'Llegada marcada a las '
                f'{timezone.localtime(turno.hora_llegada).strftime("%H:%M")}.'
            )
        else:
            turno.hora_llegada = None
            turno.llegada_marcada_por = None
            turno.hora_salida = None
            turno.motivo_salida = ''
            turno.salida_marcada_por = None
            accion = 'Llegada deshecha.'

        turno.save(update_fields=[
            'hora_llegada',
            'llegada_marcada_por',
            'hora_salida',
            'motivo_salida',
            'salida_marcada_por',
            'modificado',
        ])
        self.registrar_acceso(request, turno, detalle=accion)

        if turno.hora_llegada is None:
            messages.success(
                request,
                'Se deshizo la llegada del paciente.',
            )
        else:
            messages.success(
                request,
                'Llegada registrada. El paciente está en sala de espera.',
            )
        return redirect(url_de_retorno(request, destino))


class SalidaSalaView(
    RecepcionOProfesionalMixin,
    LoginRequiredMixin,
    AuditoriaMixin,
    View,
):
    """Registra que el paciente pasó a consultorio o se retiró de la sala."""

    accion = 'editar'
    modelo = 'Turno'

    def post(self, request, pk):
        consulta = Turno.objects.select_related('paciente', 'profesional')
        if self.profesional:
            # Un turno de otro profesional no existe para este usuario.
            consulta = consulta.filter(profesional=self.profesional)
        turno = get_object_or_404(consulta, pk=pk)

        fecha_turno = timezone.localtime(turno.fecha_hora).date()
        destino = agenda_con_filtros(request, fecha_turno)

        def volver():
            return redirect(url_de_retorno(request, destino))

        motivo = request.POST.get('motivo', '')

        if self.profesional:
            if not settings.PROFESIONAL_PUEDE_LLAMAR_PACIENTE:
                raise PermissionDenied(
                    'No tenés permiso para llamar pacientes desde la agenda.'
                )
            if motivo != MotivoSalida.ATENDIENDO:
                raise PermissionDenied(
                    'Solo recepción puede registrar que el paciente se retiró.'
                )
        elif motivo not in MotivoSalida.values:
            messages.error(
                request,
                'El motivo de salida indicado no es válido.',
            )
            return volver()

        if fecha_turno != timezone.localdate():
            messages.error(
                request,
                'Solo se puede registrar la salida el día del turno.',
            )
            return volver()

        if turno.estado not in ESTADOS_EN_SALA:
            messages.error(
                request,
                'Solo se puede registrar la salida de turnos pendientes '
                'o confirmados.',
            )
            return volver()

        if turno.hora_llegada is None:
            messages.error(
                request,
                'El paciente todavía no llegó a la sala de espera.',
            )
            return volver()

        if turno.hora_salida is not None:
            messages.error(
                request,
                'El paciente ya había salido de la sala de espera.',
            )
            return volver()

        ahora = timezone.now()
        turno.hora_salida = ahora
        turno.motivo_salida = motivo
        turno.salida_marcada_por = request.user
        turno.save(update_fields=[
            'hora_salida',
            'motivo_salida',
            'salida_marcada_por',
            'modificado',
        ])

        detalle = (
            f'Salida de la sala: {turno.get_motivo_salida_display()} '
            f'a las {timezone.localtime(ahora).strftime("%H:%M")}.'
        )
        self.registrar_acceso(request, turno, detalle=detalle)

        if motivo == MotivoSalida.ATENDIENDO:
            messages.success(request, 'El paciente pasó a consultorio.')
        else:
            messages.success(
                request,
                'El paciente se retiró de la sala de espera.',
            )
        return volver()


class VolvioSalaView(
    RecepcionOProfesionalMixin,
    LoginRequiredMixin,
    AuditoriaMixin,
    View,
):
    """Reingresa a la sala a un paciente que había salido.

    Recepción/Admin pueden hacerlo con cualquier turno y el profesional
    únicamente con sus propios turnos (los ajenos responden 404).
    """

    accion = 'editar'
    modelo = 'Turno'

    def post(self, request, pk):
        consulta = Turno.objects.select_related('paciente', 'profesional')
        if self.profesional:
            consulta = consulta.filter(profesional=self.profesional)
        turno = get_object_or_404(consulta, pk=pk)

        fecha_turno = timezone.localtime(turno.fecha_hora).date()
        destino = agenda_con_filtros(request, fecha_turno)

        def volver():
            return redirect(url_de_retorno(request, destino))

        if fecha_turno != timezone.localdate():
            messages.error(
                request,
                'Solo se puede reingresar a la sala el día del turno.',
            )
            return volver()

        if turno.estado not in ESTADOS_EN_SALA:
            messages.error(
                request,
                'Solo se puede reingresar a la sala un turno pendiente '
                'o confirmado.',
            )
            return volver()

        if turno.hora_llegada is None:
            messages.error(
                request,
                'El paciente todavía no llegó a la sala de espera.',
            )
            return volver()

        if turno.hora_salida is None:
            messages.error(
                request,
                'El paciente no había salido de la sala de espera.',
            )
            return volver()

        llegada_anterior = timezone.localtime(
            turno.hora_llegada
        ).strftime('%H:%M')
        ahora = timezone.now()
        turno.hora_llegada = ahora
        turno.llegada_marcada_por = request.user
        turno.hora_salida = None
        turno.motivo_salida = ''
        turno.salida_marcada_por = None
        turno.save(update_fields=[
            'hora_llegada',
            'llegada_marcada_por',
            'hora_salida',
            'motivo_salida',
            'salida_marcada_por',
            'modificado',
        ])

        detalle = (
            'Volvió a la sala de espera. '
            f'Llegada anterior: {llegada_anterior}. '
            f'Nueva llegada: {timezone.localtime(ahora).strftime("%H:%M")}.'
        )
        self.registrar_acceso(request, turno, detalle=detalle)

        messages.success(
            request,
            'El paciente volvió a la sala de espera.',
        )
        return volver()


class RegistrarPagoView(SoloRecepcionMixin, LoginRequiredMixin, AuditoriaMixin, View):
    """Registro interno del cobro de un turno (Recepción/Admin)."""

    accion = 'editar'
    modelo = 'Turno'
    template_name = 'turnos/pago_formulario.html'

    def get_turno(self, pk):
        return get_object_or_404(
            Turno.objects.select_related('paciente', 'profesional'),
            pk=pk,
        )

    def volver_a_la_agenda(self, turno):
        fecha = timezone.localtime(turno.fecha_hora).date().isoformat()
        return redirect(f"{reverse('turnos:agenda')}?fecha={fecha}")

    def pago_bloqueado(self, request, turno):
        if turno.permite_registrar_pago:
            return False
        messages.error(
            request,
            'No se puede registrar un pago en un turno cancelado o ausente.',
        )
        return True

    def contexto(self, turno, form):
        return {
            'turno': turno,
            'form': form,
            'es_correccion': turno.pago_registrado,
        }

    def get(self, request, pk):
        turno = self.get_turno(pk)
        if self.pago_bloqueado(request, turno):
            return self.volver_a_la_agenda(turno)

        return render(
            request,
            self.template_name,
            self.contexto(turno, PagoTurnoForm(instance=turno)),
        )

    def post(self, request, pk):
        turno = self.get_turno(pk)
        if self.pago_bloqueado(request, turno):
            return self.volver_a_la_agenda(turno)

        forma_anterior = turno.forma_pago
        monto_anterior = turno.monto
        fecha_anterior = turno.fecha_pago

        form = PagoTurnoForm(request.POST, instance=turno)
        if not form.is_valid():
            turno.refresh_from_db()
            return render(
                request,
                self.template_name,
                self.contexto(turno, form),
            )

        with transaction.atomic():
            pago = form.save(commit=False)
            es_correccion = fecha_anterior is not None
            if not es_correccion:
                pago.fecha_pago = timezone.now()
            pago.pago_registrado_por = request.user
            pago.save(update_fields=[
                'forma_pago',
                'monto',
                'fecha_pago',
                'pago_registrado_por',
                'modificado',
            ])

            if es_correccion:
                detalle = (
                    'Pago corregido. '
                    f'Anterior: {texto_pago(forma_anterior, monto_anterior)} '
                    f'(registrado el '
                    f'{timezone.localtime(fecha_anterior).strftime("%d/%m/%Y %H:%M")}). '
                    f'Nuevo: {texto_pago(pago.forma_pago, pago.monto)}.'
                )
            else:
                detalle = (
                    'Pago registrado: '
                    f'{texto_pago(pago.forma_pago, pago.monto)}.'
                )

            self.registrar_acceso(
                request,
                pago,
                accion='editar' if es_correccion else 'crear',
                detalle=detalle,
            )

        if es_correccion:
            messages.success(
                request,
                'Pago corregido. El valor anterior y el nuevo quedaron en auditoría.',
            )
        else:
            messages.success(request, 'Pago registrado correctamente.')

        return self.volver_a_la_agenda(pago)


class SolicitudTurnoCreateView(
    RecepcionOProfesionalMixin,
    LoginRequiredMixin,
    AuditoriaMixin,
    View,
):
    """El profesional pide el próximo turno de un paciente que atiende."""

    template_name = 'turnos/solicitud_formulario.html'
    accion = 'crear'
    modelo = 'SolicitudTurno'

    def get_profesional(self):
        if self.profesional is None:
            raise PermissionDenied(
                'Solo los profesionales pueden solicitar próximos turnos.'
            )
        return self.profesional

    def get_paciente(self):
        return get_object_or_404(
            Paciente.objects.atendidos_por(self.get_profesional()),
            pk=self.kwargs['paciente_pk'],
        )

    def get_solicitud_pendiente(self, paciente):
        return SolicitudTurno.objects.filter(
            paciente=paciente,
            profesional=self.get_profesional(),
            estado=EstadoSolicitud.PENDIENTE,
        ).first()

    def contexto(self, paciente, form, solicitud):
        return {
            'paciente': paciente,
            'profesional': self.get_profesional(),
            'form': form,
            'solicitud': solicitud,
            'titulo': (
                'Actualizar próximo turno'
                if solicitud else 'Solicitar próximo turno'
            ),
        }

    def get(self, request, paciente_pk):
        paciente = self.get_paciente()
        solicitud = self.get_solicitud_pendiente(paciente)
        form = SolicitudTurnoForm(instance=solicitud)
        return render(
            request,
            self.template_name,
            self.contexto(paciente, form, solicitud),
        )

    def post(self, request, paciente_pk):
        paciente = self.get_paciente()
        profesional = self.get_profesional()
        solicitud_existente = self.get_solicitud_pendiente(paciente)
        form = SolicitudTurnoForm(
            request.POST,
            instance=solicitud_existente,
        )

        if not form.is_valid():
            return render(
                request,
                self.template_name,
                self.contexto(paciente, form, solicitud_existente),
            )

        datos = form.save(commit=False)
        solicitud, creada = SolicitudTurno.objects.update_or_create(
            paciente=paciente,
            profesional=profesional,
            estado=EstadoSolicitud.PENDIENTE,
            defaults={
                'solicitado_por': request.user,
                'plazo': datos.plazo,
                'fecha_sugerida': datos.fecha_sugerida,
                'nota': datos.nota,
                'turno': None,
                'resuelto_en': None,
                'resuelto_por': None,
                'motivo_resolucion': '',
            },
        )

        self.registrar_acceso(
            request,
            solicitud,
            accion='crear' if creada else 'editar',
            detalle=(
                f'Solicitud de próximo turno para el '
                f'{solicitud.fecha_sugerida:%d/%m/%Y} '
                f'({solicitud.get_plazo_display()}).'
            ),
        )

        if creada:
            messages.success(
                request,
                'Solicitud enviada. Recepción la verá en '
                '"Turnos por agendar".',
            )
        else:
            messages.success(request, 'Solicitud actualizada.')
        return redirect('pacientes:detalle', pk=paciente.pk)


class TurnosPorAgendarView(
    SoloRecepcionMixin,
    LoginRequiredMixin,
    ListView,
):
    """Cola de solicitudes pendientes para Recepción y Administración."""

    model = SolicitudTurno
    template_name = 'turnos/por_agendar.html'
    context_object_name = 'solicitudes'

    def get_queryset(self):
        return SolicitudTurno.objects.filter(
            estado=EstadoSolicitud.PENDIENTE
        ).select_related(
            'paciente',
            'profesional',
            'solicitado_por',
        ).order_by('fecha_sugerida', 'creado')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        solicitudes = list(ctx['solicitudes'])
        ctx['solicitudes'] = solicitudes
        ctx['total_pendientes'] = len(solicitudes)
        ctx['total_vencidas'] = sum(
            1 for solicitud in solicitudes if solicitud.esta_vencida
        )
        ctx['hoy'] = timezone.localdate()
        return ctx


class DescartarSolicitudView(
    SoloRecepcionMixin,
    LoginRequiredMixin,
    AuditoriaMixin,
    View,
):
    """Descarta una solicitud pendiente con motivo opcional."""

    accion = 'editar'
    modelo = 'SolicitudTurno'

    def post(self, request, pk):
        solicitud = get_object_or_404(
            SolicitudTurno.objects.select_related('paciente', 'profesional'),
            pk=pk,
        )

        if solicitud.estado != EstadoSolicitud.PENDIENTE:
            messages.warning(
                request,
                'La solicitud ya había sido resuelta.',
            )
            return redirect('turnos:por_agendar')

        form = DescartarSolicitudForm(request.POST)
        motivo = ''
        if form.is_valid():
            motivo = (form.cleaned_data.get('motivo') or '').strip()

        solicitud.estado = EstadoSolicitud.DESCARTADA
        solicitud.resuelto_en = timezone.now()
        solicitud.resuelto_por = request.user
        solicitud.motivo_resolucion = motivo
        solicitud.save(update_fields=[
            'estado',
            'resuelto_en',
            'resuelto_por',
            'motivo_resolucion',
        ])

        self.registrar_acceso(
            request,
            solicitud,
            detalle=(
                'Solicitud descartada. Motivo: '
                f'{motivo or "sin motivo indicado"}.'
            ),
        )
        messages.success(request, 'Solicitud descartada.')
        return redirect('turnos:por_agendar')

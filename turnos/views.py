from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse, reverse_lazy
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from datetime import date, timedelta
import csv
from .models import Turno, EstadoTurno
from .forms import PagoTurnoForm, TurnoForm
from .utils import texto_pago
from historias.models import AdjuntoHistoria
from profesionales.models import Profesional
from pacientes.models import Paciente
from auditoria.mixins import AuditoriaMixin
from consultorio_salto.permisos import (
    RecepcionOProfesionalMixin,
    SoloRecepcionMixin,
)


class TurnoAgendaView(RecepcionOProfesionalMixin, LoginRequiredMixin, ListView):
    model = Turno
    template_name = 'turnos/agenda.html'
    context_object_name = 'turnos'

    def get_queryset(self):
        qs = Turno.objects.select_related(
            'paciente', 'profesional', 'pago_registrado_por'
        ).prefetch_related('profesional__especialidades').annotate(
            num_adjuntos=Count('adjuntos_historia', distinct=True)
        )
        if self.profesional:
            qs = qs.filter(profesional=self.profesional)
        fecha_str = self.request.GET.get('fecha')
        especialidad = self.request.GET.get('especialidad', '')
        profesional_id = self.request.GET.get('profesional', '')
        q = self.request.GET.get('q', '').strip()

        if fecha_str:
            try:
                from datetime import datetime
                fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            except ValueError:
                fecha = date.today()
        else:
            fecha = date.today()

        self.fecha_seleccionada = fecha
        qs = qs.filter(fecha_hora__date=fecha)

        if especialidad:
            qs = qs.filter(
                profesional__especialidades__nombre__iexact=especialidad
            ).distinct()
        if profesional_id:
            qs = qs.filter(profesional_id=profesional_id)
        if q:
            qs = qs.filter(
                Q(paciente__nombre__icontains=q) |
                Q(paciente__apellido__icontains=q) |
                Q(paciente__dni__icontains=q)
            )

        return qs.order_by('fecha_hora')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['vista'] = self.request.GET.get('vista', 'lista')
        ctx['fecha_seleccionada'] = self.fecha_seleccionada
        ctx['hoy'] = date.today()
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
        ctx['total_dia'] = self.get_queryset().count()
        # Stats rápidas del día (para profesionales, solo sus turnos)
        todos_dia = Turno.objects.filter(fecha_hora__date=self.fecha_seleccionada)
        if self.profesional:
            todos_dia = todos_dia.filter(profesional=self.profesional)
        ctx['stats_dia'] = {
            'pendientes': todos_dia.filter(estado='pendiente').count(),
            'confirmados': todos_dia.filter(estado='confirmado').count(),
            'realizados': todos_dia.filter(estado='realizado').count(),
            'ausentes': todos_dia.filter(estado='ausente').count(),
        }
        
        # Datos para el calendario mensual
        import calendar
        from datetime import datetime
        
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
                'es_hoy': dia == date.today().day and mes == date.today().month and anio == date.today().year,
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
        
        return ctx


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
        fecha_str = request.GET.get('fecha')
        try:
            from datetime import datetime
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date() if fecha_str else date.today()
        except ValueError:
            fecha = date.today()

        turnos = Turno.objects.filter(
            fecha_hora__date=fecha
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

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Nuevo Turno'
        return ctx

    def get_initial(self):
        initial = super().get_initial()
        paciente_id = self.request.GET.get('paciente')
        if paciente_id:
            initial['paciente'] = paciente_id
        return initial

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


class CambiarEstadoTurnoView(SoloRecepcionMixin, LoginRequiredMixin, View):
    def post(self, request, pk, estado):
        turno = get_object_or_404(Turno, pk=pk)
        estados_validos = [e.value for e in EstadoTurno]
        if estado in estados_validos:
            turno.estado = estado
            turno.save()
        return redirect('turnos:agenda')


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

from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.utils import timezone
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from datetime import date, timedelta
import csv
from .models import Turno, EstadoTurno
from .forms import TurnoForm
from profesionales.models import Profesional
from pacientes.models import Paciente
from auditoria.mixins import AuditoriaMixin


class TurnoAgendaView(LoginRequiredMixin, ListView):
    model = Turno
    template_name = 'turnos/agenda.html'
    context_object_name = 'turnos'

    def get_queryset(self):
        qs = Turno.objects.select_related('paciente', 'profesional')
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
            qs = qs.filter(especialidad=especialidad)
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
        ctx['especialidades'] = Profesional.objects.values_list('especialidad', flat=True).distinct()
        ctx['profesionales'] = Profesional.objects.filter(activo=True)
        ctx['filtro_especialidad'] = self.request.GET.get('especialidad', '')
        ctx['filtro_profesional'] = self.request.GET.get('profesional', '')
        ctx['q'] = self.request.GET.get('q', '')
        ctx['total_dia'] = self.get_queryset().count()
        # Stats rápidas del día
        todos_dia = Turno.objects.filter(fecha_hora__date=self.fecha_seleccionada)
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
        ).select_related('paciente', 'profesional')
        
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
                'especialidad': turno.especialidad,
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


class BuscarPacientesView(LoginRequiredMixin, View):
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


class BuscarProfesionalesView(LoginRequiredMixin, View):
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
                Q(especialidad__icontains=q)
            ).filter(activo=True).order_by('apellido', 'nombre')[:20]
        
        data = [{
            'id': p.pk,
            'nombre': p.nombre,
            'apellido': p.apellido,
            'especialidad': p.especialidad,
            'nombre_completo': f'{p.apellido}, {p.nombre}',
        } for p in profesionales]
        
        return JsonResponse({'results': data})


class ExportarAgendaCSVView(LoginRequiredMixin, AuditoriaMixin, View):
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

        turnos = Turno.objects.filter(fecha_hora__date=fecha).select_related('paciente', 'profesional').order_by('fecha_hora')

        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="agenda_{fecha.strftime("%Y%m%d")}.csv"'
        response.write('\ufeff')  # BOM para Excel

        writer = csv.writer(response)
        writer.writerow(['Hora', 'Paciente', 'DNI', 'Especialidad', 'Profesional', 'Estado', 'Motivo', 'Observaciones'])
        for t in turnos:
            writer.writerow([
                t.fecha_hora.strftime('%H:%M'),
                f'{t.paciente.apellido}, {t.paciente.nombre}',
                t.paciente.dni,
                t.especialidad,
                f'{t.profesional.apellido}, {t.profesional.nombre}',
                t.get_estado_display(),
                t.motivo,
                t.observaciones,
            ])

        return response


class TurnoCreateView(LoginRequiredMixin, AuditoriaMixin, CreateView):
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
        response = super().form_valid(form)
        self.registrar_acceso(self.request, form.instance)
        return response


class TurnoUpdateView(LoginRequiredMixin, AuditoriaMixin, UpdateView):
    model = Turno
    form_class = TurnoForm
    template_name = 'turnos/formulario.html'
    success_url = reverse_lazy('turnos:agenda')
    accion = 'editar'
    modelo = 'Turno'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Editar Turno'
        return ctx

    def form_valid(self, form):
        response = super().form_valid(form)
        self.registrar_acceso(self.request, form.instance)
        return response


class TurnoDeleteView(LoginRequiredMixin, DeleteView):
    model = Turno
    template_name = 'turnos/confirmar_eliminar.html'
    success_url = reverse_lazy('turnos:agenda')


class CambiarEstadoTurnoView(LoginRequiredMixin, View):
    def post(self, request, pk, estado):
        turno = get_object_or_404(Turno, pk=pk)
        estados_validos = [e.value for e in EstadoTurno]
        if estado in estados_validos:
            turno.estado = estado
            turno.save()
        return redirect('turnos:agenda')

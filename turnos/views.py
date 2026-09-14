from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.utils import timezone
from django.db.models import Q
from django.http import HttpResponse
from datetime import date, timedelta
import csv
from .models import Turno, EstadoTurno
from .forms import TurnoForm
from profesionales.models import Profesional


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
        return ctx


class ExportarAgendaCSVView(LoginRequiredMixin, View):
    def get(self, request):
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


class TurnoCreateView(LoginRequiredMixin, CreateView):
    model = Turno
    form_class = TurnoForm
    template_name = 'turnos/formulario.html'
    success_url = reverse_lazy('turnos:agenda')

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


class TurnoUpdateView(LoginRequiredMixin, UpdateView):
    model = Turno
    form_class = TurnoForm
    template_name = 'turnos/formulario.html'
    success_url = reverse_lazy('turnos:agenda')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Editar Turno'
        return ctx


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

from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from datetime import date, timedelta
from pacientes.models import Paciente
from profesionales.models import Profesional
from turnos.models import Turno, EstadoTurno
from historias.models import Consulta
from consultorio_salto.permisos import RecepcionOProfesionalMixin


class DashboardView(RecepcionOProfesionalMixin, LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/index.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        hoy = date.today()
        turnos_hoy = Turno.objects.filter(fecha_hora__date=hoy)

        if self.profesional:
            pacientes = Paciente.objects.atendidos_por(self.profesional)
            turnos_hoy = turnos_hoy.filter(profesional=self.profesional)
            consultas = Consulta.objects.filter(profesional=self.profesional)
            ctx['total_profesionales'] = 1
        else:
            pacientes = Paciente.objects.all()
            consultas = Consulta.objects.all()
            ctx['total_profesionales'] = Profesional.objects.filter(activo=True).count()

        ctx['total_pacientes'] = pacientes.count()
        ctx['turnos_hoy'] = turnos_hoy.count()
        ctx['turnos_pendientes'] = turnos_hoy.filter(estado=EstadoTurno.PENDIENTE).count()
        ctx['turnos_hoy_lista'] = turnos_hoy.select_related('paciente', 'profesional').order_by('fecha_hora')[:8]
        ctx['pacientes_recientes'] = pacientes.order_by('-fecha_alta')[:5]
        ctx['consultas_recientes'] = consultas.select_related('paciente', 'profesional').order_by('-fecha_hora')[:5]
        ctx['hoy'] = hoy

        # Resumen semana actual (lunes a domingo)
        lunes = hoy - timedelta(days=hoy.weekday())
        semana = []
        nombres_dias = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
        for i in range(7):
            dia = lunes + timedelta(days=i)
            turnos_dia = Turno.objects.filter(fecha_hora__date=dia)
            if self.profesional:
                turnos_dia = turnos_dia.filter(profesional=self.profesional)
            total = turnos_dia.count()
            realizados = turnos_dia.filter(estado='realizado').count()
            semana.append({
                'nombre': nombres_dias[i],
                'fecha': dia,
                'es_hoy': dia == hoy,
                'total': total,
                'realizados': realizados,
            })
        ctx['semana'] = semana

        # Próximos turnos (mañana)
        manana = hoy + timedelta(days=1)
        turnos_manana = Turno.objects.filter(fecha_hora__date=manana)
        if self.profesional:
            turnos_manana = turnos_manana.filter(profesional=self.profesional)
        ctx['turnos_manana'] = turnos_manana.select_related('paciente', 'profesional').order_by('fecha_hora')[:5]
        ctx['count_manana'] = turnos_manana.count()

        return ctx

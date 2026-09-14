from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from datetime import date, timedelta
from pacientes.models import Paciente
from profesionales.models import Profesional
from turnos.models import Turno, EstadoTurno
from historias.models import Consulta


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/index.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        hoy = date.today()
        turnos_hoy = Turno.objects.filter(fecha_hora__date=hoy)

        ctx['total_pacientes'] = Paciente.objects.count()
        ctx['total_profesionales'] = Profesional.objects.filter(activo=True).count()
        ctx['turnos_hoy'] = turnos_hoy.count()
        ctx['turnos_pendientes'] = turnos_hoy.filter(estado=EstadoTurno.PENDIENTE).count()
        ctx['turnos_hoy_lista'] = turnos_hoy.select_related('paciente', 'profesional').order_by('fecha_hora')[:8]
        ctx['pacientes_recientes'] = Paciente.objects.order_by('-fecha_alta')[:5]
        ctx['consultas_recientes'] = Consulta.objects.select_related('paciente', 'profesional').order_by('-fecha_hora')[:5]
        ctx['hoy'] = hoy

        # Resumen semana actual (lunes a domingo)
        lunes = hoy - timedelta(days=hoy.weekday())
        semana = []
        nombres_dias = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
        for i in range(7):
            dia = lunes + timedelta(days=i)
            total = Turno.objects.filter(fecha_hora__date=dia).count()
            realizados = Turno.objects.filter(fecha_hora__date=dia, estado='realizado').count()
            semana.append({
                'nombre': nombres_dias[i],
                'fecha': dia,
                'es_hoy': dia == hoy,
                'total': total,
                'realizados': realizados,
            })
        ctx['semana'] = semana

        # Próximos turnos (mañana y pasado)
        manana = hoy + timedelta(days=1)
        ctx['turnos_manana'] = Turno.objects.filter(fecha_hora__date=manana).select_related('paciente', 'profesional').order_by('fecha_hora')[:5]
        ctx['count_manana'] = Turno.objects.filter(fecha_hora__date=manana).count()

        return ctx

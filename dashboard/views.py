from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.db.models import Count, Q, Sum
from datetime import datetime, time, timedelta
from decimal import Decimal
from pacientes.models import Paciente
from profesionales.models import Profesional
from turnos.models import Turno, EstadoTurno, FormaPago
from turnos.utils import rango_del_dia
from historias.models import Consulta
from derivaciones.models import Derivacion, EstadoDerivacion
from consultorio_salto.permisos import RecepcionOProfesionalMixin, es_recepcion


class DashboardView(RecepcionOProfesionalMixin, LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/index.html'

    def get_fecha_caja(self):
        fecha_str = self.request.GET.get('fecha_caja')
        if fecha_str:
            try:
                return datetime.strptime(fecha_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        return timezone.localdate()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        hoy = timezone.localdate()
        inicio_hoy, fin_hoy = rango_del_dia(hoy)
        turnos_hoy = Turno.objects.filter(
            fecha_hora__gte=inicio_hoy,
            fecha_hora__lt=fin_hoy,
        )

        if self.profesional:
            pacientes = Paciente.objects.atendidos_por(self.profesional)
            turnos_hoy = turnos_hoy.filter(profesional=self.profesional)
            consultas = Consulta.objects.filter(profesional=self.profesional)
            ctx['total_profesionales'] = 1

            derivaciones = Derivacion.objects.filter(
                profesional_destino=self.profesional,
                estado=EstadoDerivacion.PENDIENTE,
            )
            ctx['derivaciones_pendientes'] = derivaciones.count()
            ctx['derivaciones_recientes'] = derivaciones.select_related(
                'paciente', 'profesional_origen'
            ).order_by('-creado')[:5]
        else:
            pacientes = Paciente.objects.all()
            consultas = Consulta.objects.all()
            ctx['total_profesionales'] = Profesional.objects.filter(activo=True).count()
            ctx['derivaciones_pendientes'] = 0
            ctx['derivaciones_recientes'] = []

        ctx['total_pacientes'] = pacientes.count()
        ctx['turnos_hoy'] = turnos_hoy.count()
        ctx['turnos_pendientes'] = turnos_hoy.filter(estado=EstadoTurno.PENDIENTE).count()
        ctx['en_sala_espera'] = turnos_hoy.filter(
            hora_llegada__isnull=False,
            estado__in=[EstadoTurno.PENDIENTE, EstadoTurno.CONFIRMADO],
        ).count()
        ctx['turnos_hoy_lista'] = turnos_hoy.select_related('paciente', 'profesional').order_by('fecha_hora')[:8]
        ctx['pacientes_recientes'] = pacientes.order_by('-fecha_alta')[:5]
        ctx['consultas_recientes'] = consultas.select_related('paciente', 'profesional').order_by('-fecha_hora')[:5]
        ctx['hoy'] = hoy

        # ─── Caja del día (solo Recepción/Admin) ─────────────────
        if es_recepcion(self.request.user):
            fecha_caja = self.get_fecha_caja()
            tz = timezone.get_current_timezone()
            inicio = timezone.make_aware(
                datetime.combine(fecha_caja, time.min),
                tz,
            )
            fin = inicio + timedelta(days=1)
            pagos = Turno.objects.filter(
                fecha_pago__gte=inicio,
                fecha_pago__lt=fin,
            )
            resumen = pagos.aggregate(
                efectivo=Sum(
                    'monto',
                    filter=Q(forma_pago=FormaPago.EFECTIVO),
                    default=Decimal('0.00'),
                ),
                transferencia=Sum(
                    'monto',
                    filter=Q(forma_pago=FormaPago.TRANSFERENCIA),
                    default=Decimal('0.00'),
                ),
                general=Sum(
                    'monto',
                    filter=Q(
                        forma_pago__in=[
                            FormaPago.EFECTIVO,
                            FormaPago.TRANSFERENCIA,
                        ]
                    ),
                    default=Decimal('0.00'),
                ),
                cantidad=Count(
                    'pk',
                    filter=Q(
                        forma_pago__in=[
                            FormaPago.EFECTIVO,
                            FormaPago.TRANSFERENCIA,
                        ]
                    ),
                ),
            )
            ctx['caja_fecha'] = fecha_caja
            ctx['caja'] = resumen

        # Resumen semana actual (lunes a domingo)
        lunes = hoy - timedelta(days=hoy.weekday())
        semana = []
        nombres_dias = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
        for i in range(7):
            dia = lunes + timedelta(days=i)
            inicio_dia, fin_dia = rango_del_dia(dia)
            turnos_dia = Turno.objects.filter(
                fecha_hora__gte=inicio_dia,
                fecha_hora__lt=fin_dia,
            )
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
        inicio_manana, fin_manana = rango_del_dia(manana)
        turnos_manana = Turno.objects.filter(
            fecha_hora__gte=inicio_manana,
            fecha_hora__lt=fin_manana,
        )
        if self.profesional:
            turnos_manana = turnos_manana.filter(profesional=self.profesional)
        ctx['turnos_manana'] = turnos_manana.select_related('paciente', 'profesional').order_by('fecha_hora')[:5]
        ctx['count_manana'] = turnos_manana.count()

        return ctx

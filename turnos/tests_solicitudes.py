from datetime import date, timedelta

from django.contrib.auth.models import Group, User
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from auditoria.models import LogAcceso
from consultorio_salto.context_processors import roles
from consultorio_salto.permisos import GRUPO_PROFESIONAL, GRUPO_RECEPCION
from historias.models import Consulta
from pacientes.models import Paciente
from profesionales.models import Profesional

from .models import (
    EstadoSolicitud,
    EstadoTurno,
    Plazo,
    SolicitudTurno,
    Turno,
    sumar_meses,
)


CLAVE = 'ClaveSegura2026!'


class SolicitudTurnoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        grupo_recepcion, _ = Group.objects.get_or_create(name=GRUPO_RECEPCION)
        grupo_profesional, _ = Group.objects.get_or_create(
            name=GRUPO_PROFESIONAL
        )

        cls.recepcion = User.objects.create_user(
            username='recepcion_solicitudes',
            password=CLAVE,
        )
        cls.recepcion.groups.add(grupo_recepcion)

        cls.admin = User.objects.create_superuser(
            username='admin_solicitudes',
            email='admin_solicitudes@example.com',
            password=CLAVE,
        )

        cls.user_a = User.objects.create_user(
            username='prof_solicitudes_a',
            password=CLAVE,
        )
        cls.user_a.groups.add(grupo_profesional)
        cls.user_b = User.objects.create_user(
            username='prof_solicitudes_b',
            password=CLAVE,
        )
        cls.user_b.groups.add(grupo_profesional)

        cls.prof_a = Profesional.objects.create(
            nombre='Ana',
            apellido='Solicitudes',
            dni='35000001',
            fecha_ingreso=date(2020, 1, 1),
            usuario=cls.user_a,
        )
        cls.prof_b = Profesional.objects.create(
            nombre='Beto',
            apellido='Solicitudes',
            dni='35000002',
            fecha_ingreso=date(2020, 1, 1),
            usuario=cls.user_b,
        )

        cls.paciente_a = Paciente.objects.create(
            dni='35000010',
            nombre='Paciente',
            apellido='Alfa',
            fecha_nacimiento=date(1990, 5, 5),
        )
        cls.paciente_b = Paciente.objects.create(
            dni='35000011',
            nombre='Paciente',
            apellido='Beta',
            fecha_nacimiento=date(1991, 6, 6),
        )
        cls.paciente_compartido = Paciente.objects.create(
            dni='35000012',
            nombre='Paciente',
            apellido='Compartido',
            fecha_nacimiento=date(1992, 7, 7),
        )

        # A atiende a Alfa y a Compartido; B atiende a Beta y a Compartido.
        for profesional, paciente in (
            (cls.prof_a, cls.paciente_a),
            (cls.prof_a, cls.paciente_compartido),
            (cls.prof_b, cls.paciente_b),
            (cls.prof_b, cls.paciente_compartido),
        ):
            Consulta.objects.create(
                paciente=paciente,
                profesional=profesional,
                fecha_hora=timezone.now(),
                diagnostico='Control',
            )

    def login(self, user):
        self.client.force_login(user)

    def url_solicitar(self, paciente=None):
        return reverse(
            'turnos:solicitar_turno',
            args=[(paciente or self.paciente_a).pk],
        )

    def crear_solicitud(self, paciente=None, profesional=None, **kwargs):
        datos = {
            'paciente': paciente or self.paciente_a,
            'profesional': profesional or self.prof_a,
            'fecha_sugerida': timezone.localdate() + timedelta(days=7),
            'plazo': Plazo.UNA_SEMANA,
        }
        datos.update(kwargs)
        return SolicitudTurno.objects.create(**datos)

    def test_profesional_crea_solicitud_para_paciente_que_atiende(self):
        self.login(self.user_a)
        response = self.client.post(
            self.url_solicitar(),
            {'plazo': Plazo.UNA_SEMANA, 'nota': 'Prefiere por la mañana.'},
        )

        self.assertRedirects(
            response,
            reverse('pacientes:detalle', args=[self.paciente_a.pk]),
        )
        solicitud = SolicitudTurno.objects.get()
        self.assertEqual(solicitud.paciente, self.paciente_a)
        self.assertEqual(solicitud.profesional, self.prof_a)
        self.assertEqual(solicitud.solicitado_por, self.user_a)
        self.assertEqual(solicitud.estado, EstadoSolicitud.PENDIENTE)
        self.assertEqual(
            solicitud.fecha_sugerida,
            timezone.localdate() + timedelta(days=7),
        )
        self.assertEqual(solicitud.nota, 'Prefiere por la mañana.')

        self.assertTrue(
            LogAcceso.objects.filter(
                usuario=self.user_a,
                accion='crear',
                modelo='SolicitudTurno',
                objeto_id=solicitud.pk,
            ).exists()
        )

    def test_profesional_no_puede_solicitar_para_paciente_ajeno(self):
        self.login(self.user_b)
        response = self.client.post(
            self.url_solicitar(self.paciente_a),
            {'plazo': Plazo.UNA_SEMANA, 'nota': ''},
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(SolicitudTurno.objects.exists())

    def test_recepcion_no_puede_crear_solicitud(self):
        self.login(self.recepcion)
        response = self.client.post(
            self.url_solicitar(),
            {'plazo': Plazo.UNA_SEMANA, 'nota': ''},
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(SolicitudTurno.objects.exists())

    def test_no_duplica_pendientes_y_actualiza_la_existente(self):
        self.login(self.user_a)
        self.client.post(
            self.url_solicitar(),
            {'plazo': Plazo.UNA_SEMANA, 'nota': 'Primera nota.'},
        )
        self.client.post(
            self.url_solicitar(),
            {'plazo': Plazo.DOS_MESES, 'nota': 'Nota actualizada.'},
        )

        self.assertEqual(
            SolicitudTurno.objects.filter(
                estado=EstadoSolicitud.PENDIENTE
            ).count(),
            1,
        )
        solicitud = SolicitudTurno.objects.get()
        self.assertEqual(solicitud.plazo, Plazo.DOS_MESES)
        self.assertEqual(
            solicitud.fecha_sugerida,
            sumar_meses(timezone.localdate(), 2),
        )
        self.assertEqual(solicitud.nota, 'Nota actualizada.')

        self.assertTrue(
            LogAcceso.objects.filter(
                modelo='SolicitudTurno',
                accion='editar',
                objeto_id=solicitud.pk,
            ).exists()
        )

    def test_fecha_exacta_requerida_y_guardada(self):
        self.login(self.user_a)
        response = self.client.post(
            self.url_solicitar(),
            {'plazo': Plazo.FECHA_EXACTA, 'nota': ''},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(SolicitudTurno.objects.exists())

        fecha = timezone.localdate() + timedelta(days=20)
        response = self.client.post(
            self.url_solicitar(),
            {
                'plazo': Plazo.FECHA_EXACTA,
                'fecha_exacta': fecha.isoformat(),
                'nota': '',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(SolicitudTurno.objects.get().fecha_sugerida, fecha)

    def test_flujo_completo_agendar_cierra_la_solicitud(self):
        solicitud = self.crear_solicitud(nota='Control en un mes.')
        self.login(self.recepcion)

        response = self.client.get(
            reverse('turnos:crear'),
            {'solicitud': solicitud.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Agendando la solicitud')
        self.assertContains(response, self.paciente_a.apellido)

        fecha_hora = timezone.localtime(timezone.now()).replace(
            hour=15,
            minute=30,
            second=0,
            microsecond=0,
        ) + timedelta(days=7)
        response = self.client.post(
            reverse('turnos:crear'),
            {
                'solicitud': solicitud.pk,
                'paciente': self.paciente_a.pk,
                'profesional': self.prof_a.pk,
                'fecha_hora': fecha_hora.strftime('%Y-%m-%dT%H:%M'),
                'motivo': 'Control',
                'estado': EstadoTurno.PENDIENTE,
                'observaciones': '',
            },
        )

        self.assertRedirects(response, reverse('turnos:por_agendar'))
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, EstadoSolicitud.AGENDADA)
        self.assertIsNotNone(solicitud.turno)
        self.assertEqual(solicitud.resuelto_por, self.recepcion)
        self.assertIsNotNone(solicitud.resuelto_en)
        self.assertEqual(solicitud.turno.paciente, self.paciente_a)
        self.assertEqual(solicitud.turno.profesional, self.prof_a)

        self.assertTrue(
            LogAcceso.objects.filter(
                usuario=self.recepcion,
                modelo='SolicitudTurno',
                accion='editar',
                objeto_id=solicitud.pk,
                detalle__contains='agendado',
            ).exists()
        )

    def test_agendar_con_otro_paciente_no_cierra_la_solicitud(self):
        solicitud = self.crear_solicitud()
        self.login(self.recepcion)

        fecha_hora = timezone.localtime(timezone.now()) + timedelta(days=3)
        response = self.client.post(
            reverse('turnos:crear'),
            {
                'solicitud': solicitud.pk,
                'paciente': self.paciente_b.pk,
                'profesional': self.prof_a.pk,
                'fecha_hora': fecha_hora.strftime('%Y-%m-%dT%H:%M'),
                'motivo': 'Control',
                'estado': EstadoTurno.PENDIENTE,
                'observaciones': '',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'no corresponde')
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, EstadoSolicitud.PENDIENTE)
        self.assertIsNone(solicitud.turno)
        self.assertFalse(Turno.objects.exists())

    def test_descartar_solicitud_con_motivo(self):
        solicitud = self.crear_solicitud()
        self.login(self.recepcion)

        response = self.client.post(
            reverse('turnos:descartar_solicitud', args=[solicitud.pk]),
            {'motivo': 'El paciente pidió otro profesional.'},
        )

        self.assertRedirects(response, reverse('turnos:por_agendar'))
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, EstadoSolicitud.DESCARTADA)
        self.assertEqual(
            solicitud.motivo_resolucion,
            'El paciente pidió otro profesional.',
        )
        self.assertEqual(solicitud.resuelto_por, self.recepcion)
        self.assertIsNotNone(solicitud.resuelto_en)

        self.assertTrue(
            LogAcceso.objects.filter(
                usuario=self.recepcion,
                modelo='SolicitudTurno',
                accion='editar',
                objeto_id=solicitud.pk,
                detalle__contains='descartada',
            ).exists()
        )

    def test_cola_ordenada_resalta_vencidas_y_solo_muestra_pendientes(self):
        vencida = self.crear_solicitud(
            fecha_sugerida=timezone.localdate() - timedelta(days=3),
        )
        futura = self.crear_solicitud(
            paciente=self.paciente_compartido,
            fecha_sugerida=timezone.localdate() + timedelta(days=10),
        )
        self.crear_solicitud(
            paciente=self.paciente_b,
            profesional=self.prof_b,
            estado=EstadoSolicitud.AGENDADA,
            fecha_sugerida=timezone.localdate() + timedelta(days=1),
        )

        self.login(self.recepcion)
        response = self.client.get(reverse('turnos:por_agendar'))

        self.assertEqual(response.status_code, 200)
        solicitudes = list(response.context['solicitudes'])
        self.assertEqual(solicitudes, [vencida, futura])
        self.assertTrue(vencida.esta_vencida)
        self.assertFalse(futura.esta_vencida)
        self.assertContains(response, 'Vencida')
        self.assertEqual(response.context['total_pendientes'], 2)
        self.assertEqual(response.context['total_vencidas'], 1)

    def test_contador_de_pendientes_solo_para_recepcion(self):
        self.crear_solicitud()
        self.crear_solicitud(
            paciente=self.paciente_compartido,
            fecha_sugerida=timezone.localdate() + timedelta(days=15),
        )
        self.crear_solicitud(
            paciente=self.paciente_b,
            profesional=self.prof_b,
            estado=EstadoSolicitud.DESCARTADA,
        )

        factory = RequestFactory()

        request = factory.get('/')
        request.user = self.recepcion
        self.assertEqual(roles(request)['solicitudes_pendientes_count'], 2)

        request = factory.get('/')
        request.user = self.admin
        self.assertEqual(roles(request)['solicitudes_pendientes_count'], 2)

        request = factory.get('/')
        request.user = self.user_a
        self.assertEqual(roles(request)['solicitudes_pendientes_count'], 0)

        from django.contrib.auth.models import AnonymousUser

        request = factory.get('/')
        request.user = AnonymousUser()
        self.assertEqual(roles(request)['solicitudes_pendientes_count'], 0)

        # El menú lateral muestra el contador para recepción.
        self.login(self.recepcion)
        response = self.client.get(reverse('dashboard:index'))
        self.assertContains(response, 'Turnos por agendar')
        self.assertContains(response, 'nav-badge')

        # El profesional no ve la cola ni el contador en el menú.
        self.login(self.user_a)
        response = self.client.get(reverse('dashboard:index'))
        self.assertNotContains(response, 'Turnos por agendar')

    def test_permisos_de_la_pantalla_por_agendar(self):
        self.login(self.user_a)
        self.assertEqual(
            self.client.get(reverse('turnos:por_agendar')).status_code,
            403,
        )

        self.login(self.recepcion)
        self.assertEqual(
            self.client.get(reverse('turnos:por_agendar')).status_code,
            200,
        )

        self.login(self.admin)
        self.assertEqual(
            self.client.get(reverse('turnos:por_agendar')).status_code,
            200,
        )

        self.client.logout()
        response = self.client.get(reverse('turnos:por_agendar'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_ficha_del_paciente_muestra_el_estado_de_la_solicitud(self):
        solicitud = self.crear_solicitud(nota='Prefiere turnos vespertinos.')
        self.login(self.user_a)

        response = self.client.get(
            reverse('pacientes:detalle', args=[self.paciente_a.pk])
        )
        self.assertContains(response, 'Pendiente de agendar')
        self.assertContains(response, 'Prefiere turnos vespertinos.')
        self.assertContains(response, reverse('turnos:solicitar_turno', args=[self.paciente_a.pk]))

        solicitud.estado = EstadoSolicitud.AGENDADA
        solicitud.turno = Turno.objects.create(
            paciente=self.paciente_a,
            profesional=self.prof_a,
            fecha_hora=timezone.now() + timedelta(days=7),
        )
        solicitud.save()

        response = self.client.get(
            reverse('pacientes:detalle', args=[self.paciente_a.pk])
        )
        self.assertContains(response, 'Agendada')
        self.assertContains(
            response,
            timezone.localtime(solicitud.turno.fecha_hora).strftime('%d/%m/%Y'),
        )

        solicitud.estado = EstadoSolicitud.DESCARTADA
        solicitud.motivo_resolucion = 'Se descartó por pedido del paciente.'
        solicitud.save()

        response = self.client.get(
            reverse('pacientes:detalle', args=[self.paciente_a.pk])
        )
        self.assertContains(response, 'Descartada')
        self.assertContains(response, 'Se descartó por pedido del paciente.')

    def test_profesional_solo_ve_su_propia_solicitud_en_la_ficha(self):
        self.crear_solicitud(
            paciente=self.paciente_compartido,
            profesional=self.prof_b,
            nota='Solicitud de B.',
        )
        self.login(self.user_a)

        response = self.client.get(
            reverse('pacientes:detalle', args=[self.paciente_compartido.pk])
        )
        self.assertContains(
            response,
            'No hay una solicitud de próximo turno para este paciente.',
        )
        self.assertNotContains(response, 'Solicitud de B.')

    def test_la_solicitud_vencida_no_bloquea_una_nueva(self):
        solicitud = self.crear_solicitud(
            fecha_sugerida=timezone.localdate() - timedelta(days=5),
        )
        self.login(self.user_a)

        response = self.client.post(
            self.url_solicitar(),
            {'plazo': Plazo.UNA_SEMANA, 'nota': 'Reprogramar.'},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(SolicitudTurno.objects.count(), 1)
        solicitud.refresh_from_db()
        self.assertEqual(
            solicitud.fecha_sugerida,
            timezone.localdate() + timedelta(days=7),
        )
        self.assertEqual(solicitud.nota, 'Reprogramar.')

    def test_plazos_calculan_la_fecha_sugerida(self):
        hoy = date(2026, 1, 31)
        self.assertEqual(
            self._fecha(Plazo.UNA_SEMANA, base=hoy),
            date(2026, 2, 7),
        )
        self.assertEqual(
            self._fecha(Plazo.QUINCE_DIAS, base=hoy),
            date(2026, 2, 15),
        )
        self.assertEqual(
            self._fecha(Plazo.UN_MES, base=hoy),
            date(2026, 2, 28),
        )
        self.assertEqual(
            self._fecha(Plazo.DOS_MESES, base=hoy),
            date(2026, 3, 31),
        )
        self.assertEqual(
            self._fecha(Plazo.TRES_MESES, base=hoy),
            date(2026, 4, 30),
        )
        self.assertEqual(
            self._fecha(
                Plazo.FECHA_EXACTA,
                fecha_exacta=date(2026, 5, 20),
                base=hoy,
            ),
            date(2026, 5, 20),
        )

    @staticmethod
    def _fecha(plazo, fecha_exacta=None, base=None):
        from .models import calcular_fecha_sugerida

        return calcular_fecha_sugerida(plazo, fecha_exacta, base)

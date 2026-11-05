from datetime import date, datetime, time, timedelta
from urllib.parse import parse_qs, urlparse

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from auditoria.models import LogAcceso
from pacientes.models import Paciente
from profesionales.models import Profesional

from .models import EstadoTurno, Turno


CLAVE = 'ClaveSegura2026!'


class BaseLlegadaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.grupo_recepcion, _ = Group.objects.get_or_create(
            name='Recepcion'
        )
        cls.grupo_profesional, _ = Group.objects.get_or_create(
            name='Profesional'
        )

        cls.recepcion = User.objects.create_user(
            username='recepcion_llegada',
            password=CLAVE,
        )
        cls.recepcion.groups.add(cls.grupo_recepcion)

        cls.admin = User.objects.create_superuser(
            username='admin_llegada',
            email='admin_llegada@example.com',
            password=CLAVE,
        )

        cls.user_profesional = User.objects.create_user(
            username='profesional_llegada',
            password=CLAVE,
        )
        cls.user_profesional.groups.add(cls.grupo_profesional)

        cls.profesional = Profesional.objects.create(
            nombre='Ana',
            apellido='García',
            dni='30555111',
            email='ana.llegada@example.com',
            fecha_ingreso=date(2020, 1, 15),
            usuario=cls.user_profesional,
        )

        cls.otro_user_profesional = User.objects.create_user(
            username='otro_profesional_llegada',
            password=CLAVE,
        )
        cls.otro_user_profesional.groups.add(cls.grupo_profesional)
        cls.otro_profesional = Profesional.objects.create(
            nombre='Bruno',
            apellido='López',
            dni='30555222',
            email='bruno.llegada@example.com',
            fecha_ingreso=date(2020, 1, 15),
            usuario=cls.otro_user_profesional,
        )

        cls.sin_rol = User.objects.create_user(
            username='sin_rol_llegada',
            password=CLAVE,
        )

        cls.paciente = Paciente.objects.create(
            dni='31555111',
            nombre='Lucía',
            apellido='Fernández',
            fecha_nacimiento=date(1985, 4, 12),
        )
        cls.otro_paciente = Paciente.objects.create(
            dni='31555222',
            nombre='Mario',
            apellido='Suárez',
            fecha_nacimiento=date(1978, 6, 20),
        )

    def setUp(self):
        self.hoy = timezone.localdate()
        self.turno = self.crear_turno(
            paciente=self.paciente,
            profesional=self.profesional,
            hora=10,
        )

    def crear_turno(
        self,
        paciente=None,
        profesional=None,
        hora=10,
        fecha=None,
        estado=EstadoTurno.CONFIRMADO,
    ):
        fecha = fecha or self.hoy
        fecha_hora = timezone.make_aware(
            datetime.combine(fecha, time(hora, 0))
        )
        return Turno.objects.create(
            paciente=paciente or self.paciente,
            profesional=profesional or self.profesional,
            fecha_hora=fecha_hora,
            motivo='Control',
            estado=estado,
        )

    def marcar_llegada(self, turno, minutos_atras=10):
        turno.hora_llegada = timezone.now() - timedelta(
            minutes=minutos_atras
        )
        turno.llegada_marcada_por = self.recepcion
        turno.save(update_fields=['hora_llegada', 'llegada_marcada_por'])
        return turno

    def url_llegada(self, turno):
        return reverse('turnos:llegada', args=[turno.pk])

    def url_agenda(self, **params):
        return reverse('turnos:agenda') + '?' + '&'.join(
            f'{clave}={valor}' for clave, valor in params.items()
        )


class MarcarLlegadaTests(BaseLlegadaTests):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.recepcion)

    def test_recepcion_marca_y_deshace_la_llegada(self):
        response = self.client.post(
            self.url_llegada(self.turno),
            {'next': self.url_agenda(fecha=self.hoy.isoformat())},
        )
        self.assertEqual(response.status_code, 302)

        self.turno.refresh_from_db()
        self.assertIsNotNone(self.turno.hora_llegada)
        self.assertEqual(self.turno.llegada_marcada_por, self.recepcion)
        self.assertTrue(self.turno.en_sala_espera)

        log = LogAcceso.objects.filter(
            modelo='Turno',
            objeto_id=self.turno.pk,
            detalle__contains='Llegada marcada',
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.usuario, self.recepcion)
        self.assertEqual(log.accion, 'editar')

        response = self.client.post(
            self.url_llegada(self.turno),
            {'next': self.url_agenda(fecha=self.hoy.isoformat())},
        )
        self.assertEqual(response.status_code, 302)

        self.turno.refresh_from_db()
        self.assertIsNone(self.turno.hora_llegada)
        self.assertIsNone(self.turno.llegada_marcada_por)
        self.assertFalse(self.turno.en_sala_espera)
        self.assertTrue(
            LogAcceso.objects.filter(
                modelo='Turno',
                objeto_id=self.turno.pk,
                detalle__contains='Llegada deshecha',
            ).exists()
        )

    def test_admin_tambien_puede_marcar(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.url_llegada(self.turno))
        self.assertEqual(response.status_code, 302)
        self.turno.refresh_from_db()
        self.assertIsNotNone(self.turno.hora_llegada)

    def test_profesional_y_usuario_sin_rol_reciben_403(self):
        for usuario in (self.user_profesional, self.sin_rol):
            with self.subTest(usuario=usuario.username):
                self.client.force_login(usuario)
                response = self.client.post(self.url_llegada(self.turno))
                self.assertEqual(response.status_code, 403)

        self.turno.refresh_from_db()
        self.assertIsNone(self.turno.hora_llegada)

    def test_vuelve_a_la_pagina_de_origen_con_fecha_y_filtros(self):
        destino = self.url_agenda(
            fecha=self.hoy.isoformat(),
            q='Fern',
            especialidad='Cardiología',
            orden='llegada',
        )
        response = self.client.post(
            self.url_llegada(self.turno),
            {'next': destino},
        )
        self.assertRedirects(
            response,
            destino,
            fetch_redirect_response=False,
        )

    def test_next_externo_se_ignora(self):
        response = self.client.post(
            self.url_llegada(self.turno),
            {'next': 'https://sitio-malicioso.example/'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            f"{reverse('turnos:agenda')}?fecha={self.hoy.isoformat()}",
        )


class ValidacionesLlegadaTests(BaseLlegadaTests):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.recepcion)

    def test_no_se_puede_marcar_en_otra_fecha(self):
        turno_manana = self.crear_turno(
            fecha=self.hoy + timedelta(days=1),
        )
        response = self.client.post(
            self.url_llegada(turno_manana),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'Solo se puede marcar la llegada el día del turno.',
        )
        turno_manana.refresh_from_db()
        self.assertIsNone(turno_manana.hora_llegada)

    def test_no_se_puede_marcar_en_estados_terminados(self):
        for estado in (
            EstadoTurno.CANCELADO,
            EstadoTurno.REALIZADO,
            EstadoTurno.AUSENTE,
        ):
            with self.subTest(estado=estado):
                Turno.objects.filter(pk=self.turno.pk).update(estado=estado)
                response = self.client.post(
                    self.url_llegada(self.turno),
                    follow=True,
                )
                self.assertContains(
                    response,
                    'Solo se puede marcar la llegada de turnos pendientes '
                    'o confirmados.',
                )
                self.turno.refresh_from_db()
                self.assertIsNone(self.turno.hora_llegada)

    def test_turno_pendiente_permite_marcar(self):
        Turno.objects.filter(pk=self.turno.pk).update(
            estado=EstadoTurno.PENDIENTE,
        )
        response = self.client.post(self.url_llegada(self.turno))
        self.assertEqual(response.status_code, 302)
        self.turno.refresh_from_db()
        self.assertIsNotNone(self.turno.hora_llegada)


class ColaSalaEsperaTests(BaseLlegadaTests):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.recepcion)
        self.turno_temprano = self.crear_turno(hora=11)
        self.turno_tardio = self.crear_turno(hora=10)

    def test_cola_se_ordena_por_hora_de_llegada(self):
        self.marcar_llegada(self.turno_temprano, minutos_atras=25)
        self.marcar_llegada(self.turno_tardio, minutos_atras=5)

        response = self.client.get(
            reverse('turnos:agenda'),
            {'fecha': self.hoy.isoformat()},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_sala'], 2)

        cola = response.context['grupos_sala'][0]['cola']
        self.assertEqual(cola[0].pk, self.turno_temprano.pk)
        self.assertEqual(cola[1].pk, self.turno_tardio.pk)
        self.assertTrue(cola[0].resaltado_sala)
        self.assertEqual(cola[0].posicion_sala, 1)
        self.assertEqual(cola[1].posicion_sala, 2)

    def test_orden_de_llegada_pone_primero_a_quien_esta_en_sala(self):
        self.marcar_llegada(self.turno_temprano, minutos_atras=20)
        # turno_tardio tiene hora de turno anterior pero no llegó.
        response = self.client.get(
            reverse('turnos:agenda'),
            {'fecha': self.hoy.isoformat(), 'orden': 'llegada'},
        )
        ids = [turno.pk for turno in response.context['turnos']]
        self.assertEqual(ids[0], self.turno_temprano.pk)
        self.assertIn(self.turno_tardio.pk, ids)

    def test_profesional_solo_ve_su_cola(self):
        self.marcar_llegada(self.turno_temprano, minutos_atras=20)
        turno_ajeno = self.crear_turno(
            paciente=self.otro_paciente,
            profesional=self.otro_profesional,
            hora=12,
        )
        self.marcar_llegada(turno_ajeno, minutos_atras=30)

        self.client.force_login(self.user_profesional)
        response = self.client.get(
            reverse('turnos:agenda'),
            {'fecha': self.hoy.isoformat()},
        )
        self.assertEqual(response.context['total_sala'], 1)
        self.assertEqual(
            response.context['grupos_sala'][0]['cola'][0].pk,
            self.turno_temprano.pk,
        )
        self.assertNotContains(response, self.otro_paciente.apellido)

    def test_json_respeta_el_alcance_del_profesional(self):
        self.marcar_llegada(self.turno_temprano, minutos_atras=20)
        turno_ajeno = self.crear_turno(
            paciente=self.otro_paciente,
            profesional=self.otro_profesional,
            hora=12,
        )
        self.marcar_llegada(turno_ajeno, minutos_atras=30)

        self.client.force_login(self.user_profesional)
        response = self.client.get(
            reverse('turnos:sala_espera'),
            {'fecha': self.hoy.isoformat()},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        ids = [item['id'] for item in data['cola']]
        self.assertEqual(ids, [self.turno_temprano.pk])
        self.assertIn(str(self.turno_temprano.pk), data['llegadas'])
        self.assertNotIn(str(turno_ajeno.pk), data['llegadas'])

        self.client.force_login(self.recepcion)
        response = self.client.get(
            reverse('turnos:sala_espera'),
            {'fecha': self.hoy.isoformat()},
        )
        data = response.json()
        ids = [item['id'] for item in data['cola']]
        self.assertEqual(len(ids), 2)
        self.assertEqual(ids[0], turno_ajeno.pk)
        self.assertEqual(data['total'], 2)

    def test_json_incluye_hora_de_llegada_y_espera(self):
        self.marcar_llegada(self.turno, minutos_atras=12)
        response = self.client.get(
            reverse('turnos:sala_espera'),
            {'fecha': self.hoy.isoformat()},
        )
        data = response.json()
        self.assertIn(str(self.turno.pk), data['llegadas'])
        self.assertGreaterEqual(data['esperas'][str(self.turno.pk)], 11)

    def test_usuario_sin_rol_no_accede_al_json(self):
        self.client.force_login(self.sin_rol)
        response = self.client.get(
            reverse('turnos:sala_espera'),
            {'fecha': self.hoy.isoformat()},
        )
        self.assertEqual(response.status_code, 403)

    def test_panel_vacio_muestra_mensaje(self):
        response = self.client.get(
            reverse('turnos:agenda'),
            {'fecha': self.hoy.isoformat()},
        )
        self.assertContains(response, 'Nadie en sala de espera')


class CambiarEstadoAgendaTests(BaseLlegadaTests):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.recepcion)

    def test_conserva_fecha_y_filtros_y_audita(self):
        destino = self.url_agenda(
            fecha=self.hoy.isoformat(),
            q='Fern',
            orden='llegada',
        )
        response = self.client.post(
            reverse(
                'turnos:cambiar_estado',
                args=[self.turno.pk, EstadoTurno.REALIZADO],
            ),
            {'next': destino},
        )
        self.assertRedirects(
            response,
            destino,
            fetch_redirect_response=False,
        )
        self.turno.refresh_from_db()
        self.assertEqual(self.turno.estado, EstadoTurno.REALIZADO)
        log = LogAcceso.objects.filter(
            modelo='Turno',
            objeto_id=self.turno.pk,
            detalle__contains='Estado cambiado',
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.usuario, self.recepcion)

    def test_sin_next_vuelve_a_la_agenda_del_turno_con_filtros(self):
        response = self.client.post(
            reverse(
                'turnos:cambiar_estado',
                args=[self.turno.pk, EstadoTurno.CONFIRMADO],
            ),
            {
                'fecha': self.hoy.isoformat(),
                'q': 'Fern',
                'especialidad': 'Cardiología',
            },
        )
        self.assertEqual(response.status_code, 302)
        partes = urlparse(response.url)
        params = parse_qs(partes.query)
        self.assertEqual(params['fecha'][0], self.hoy.isoformat())
        self.assertEqual(params['q'][0], 'Fern')
        self.assertEqual(params['especialidad'][0], 'Cardiología')


class DashboardSalaTests(BaseLlegadaTests):
    def test_recepcion_ve_contador_e_insignia(self):
        self.marcar_llegada(self.turno, minutos_atras=10)
        self.client.force_login(self.recepcion)
        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['en_sala_espera'], 1)
        self.assertContains(response, 'En sala de espera')
        self.assertContains(response, 'En sala')

    def test_profesional_solo_cuenta_sus_turnos_en_sala(self):
        self.marcar_llegada(self.turno, minutos_atras=10)
        turno_ajeno = self.crear_turno(
            paciente=self.otro_paciente,
            profesional=self.otro_profesional,
            hora=12,
        )
        self.marcar_llegada(turno_ajeno, minutos_atras=5)

        self.client.force_login(self.user_profesional)
        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response.context['en_sala_espera'], 1)
        self.assertContains(response, self.paciente.apellido)
        self.assertNotContains(response, self.otro_paciente.apellido)

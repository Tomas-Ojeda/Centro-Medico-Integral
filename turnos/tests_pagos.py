from datetime import date, datetime, time
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from auditoria.models import LogAcceso
from pacientes.models import Paciente
from profesionales.models import Profesional

from .models import EstadoTurno, FormaPago, Turno


CLAVE = 'ClaveSegura2026!'
TZ_BUENOS_AIRES = 'America/Argentina/Buenos_Aires'


class BasePagosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.grupo_recepcion, _ = Group.objects.get_or_create(
            name='Recepcion'
        )
        cls.grupo_profesional, _ = Group.objects.get_or_create(
            name='Profesional'
        )

        cls.recepcion = User.objects.create_user(
            username='recepcion_pagos',
            password=CLAVE,
        )
        cls.recepcion.groups.add(cls.grupo_recepcion)

        cls.admin = User.objects.create_superuser(
            username='admin_pagos',
            email='admin_pagos@example.com',
            password=CLAVE,
        )

        cls.user_profesional = User.objects.create_user(
            username='prof_pagos',
            password=CLAVE,
        )
        cls.user_profesional.groups.add(cls.grupo_profesional)

        cls.sin_rol = User.objects.create_user(
            username='sin_rol_pagos',
            password=CLAVE,
        )

        cls.profesional = Profesional.objects.create(
            nombre='Ana',
            apellido='García',
            dni='30555555',
            email='ana.pagos@example.com',
            fecha_ingreso=date(2020, 1, 15),
            usuario=cls.user_profesional,
        )
        cls.paciente = Paciente.objects.create(
            dni='31555555',
            nombre='Paciente',
            apellido='Pago',
            fecha_nacimiento=date(1985, 4, 12),
        )
        cls.fecha_hora = timezone.make_aware(
            datetime.combine(date.today(), time(10, 0))
        )
        cls.turno = Turno.objects.create(
            paciente=cls.paciente,
            profesional=cls.profesional,
            fecha_hora=cls.fecha_hora,
            motivo='Control',
            estado=EstadoTurno.CONFIRMADO,
        )

    def login(self, user):
        self.client.force_login(user)

    def datos_pago(self, forma_pago=FormaPago.EFECTIVO, monto='12000.00'):
        return {
            'forma_pago': forma_pago,
            'monto': monto,
        }

    def crear_turno_pagado(self, fecha_pago, forma_pago, monto):
        turno = Turno.objects.create(
            paciente=self.paciente,
            profesional=self.profesional,
            fecha_hora=self.fecha_hora,
            motivo='Control',
            estado=EstadoTurno.REALIZADO,
            forma_pago=forma_pago,
            monto=monto,
            fecha_pago=fecha_pago,
            pago_registrado_por=self.recepcion,
        )
        return turno


class PermisosPagoTests(BasePagosTests):
    def test_recepcion_y_admin_pueden_abrir_el_formulario(self):
        for usuario in (self.recepcion, self.admin):
            self.login(usuario)
            response = self.client.get(
                reverse('turnos:registrar_pago', args=[self.turno.pk])
            )
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'Registro interno de cobro')
            self.assertContains(response, 'No es comprobante fiscal')

    def test_profesional_y_usuario_sin_rol_reciben_403(self):
        for usuario in (self.user_profesional, self.sin_rol):
            self.login(usuario)
            url = reverse('turnos:registrar_pago', args=[self.turno.pk])
            self.assertEqual(self.client.get(url).status_code, 403)
            self.assertEqual(
                self.client.post(url, self.datos_pago()).status_code,
                403,
            )

        self.turno.refresh_from_db()
        self.assertIsNone(self.turno.fecha_pago)

    def test_profesional_no_puede_registrar_pago_por_post_directo(self):
        self.login(self.user_profesional)
        response = self.client.post(
            reverse('turnos:registrar_pago', args=[self.turno.pk]),
            self.datos_pago(),
        )
        self.assertEqual(response.status_code, 403)
        self.turno.refresh_from_db()
        self.assertIsNone(self.turno.fecha_pago)


class ValidacionesPagoTests(BasePagosTests):
    def setUp(self):
        self.login(self.recepcion)
        self.url = reverse('turnos:registrar_pago', args=[self.turno.pk])

    def test_monto_negativo_rechazado(self):
        response = self.client.post(
            self.url,
            self.datos_pago(FormaPago.EFECTIVO, '-100'),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'no puede ser negativo')
        self.turno.refresh_from_db()
        self.assertIsNone(self.turno.fecha_pago)

    def test_monto_obligatorio_salvo_cobertura(self):
        response = self.client.post(
            self.url,
            self.datos_pago(FormaPago.EFECTIVO, ''),
        )
        self.assertEqual(response.status_code, 200)
        self.turno.refresh_from_db()
        self.assertIsNone(self.turno.fecha_pago)

        response = self.client.post(
            self.url,
            self.datos_pago(FormaPago.COBERTURA, ''),
        )
        self.assertEqual(response.status_code, 302)
        self.turno.refresh_from_db()
        self.assertIsNotNone(self.turno.fecha_pago)
        self.assertEqual(self.turno.forma_pago, FormaPago.COBERTURA)
        self.assertIsNone(self.turno.monto)

    def test_monto_admite_coma_como_separador_decimal(self):
        response = self.client.post(
            self.url,
            self.datos_pago(FormaPago.TRANSFERENCIA, '12.500,50'),
        )
        self.assertEqual(response.status_code, 302)
        self.turno.refresh_from_db()
        self.assertEqual(self.turno.monto, Decimal('12500.50'))

    def test_monto_con_mas_de_dos_decimales_rechazado(self):
        response = self.client.post(
            self.url,
            self.datos_pago(FormaPago.EFECTIVO, '12000,999'),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'dos decimales')
        self.turno.refresh_from_db()
        self.assertIsNone(self.turno.fecha_pago)

    def test_no_se_puede_cobrar_turno_cancelado_ni_ausente(self):
        for estado in (EstadoTurno.CANCELADO, EstadoTurno.AUSENTE):
            with self.subTest(estado=estado):
                Turno.objects.filter(pk=self.turno.pk).update(estado=estado)
                response = self.client.get(self.url)
                self.assertEqual(response.status_code, 302)

                response = self.client.post(
                    self.url,
                    self.datos_pago(),
                )
                self.assertEqual(response.status_code, 302)
                self.turno.refresh_from_db()
                self.assertIsNone(self.turno.fecha_pago)


class AuditoriaPagoTests(BasePagosTests):
    def setUp(self):
        self.login(self.recepcion)
        self.url = reverse('turnos:registrar_pago', args=[self.turno.pk])

    def test_correccion_guarda_valor_anterior_y_nuevo(self):
        self.client.post(self.url, self.datos_pago(FormaPago.EFECTIVO, '12000'))
        self.turno.refresh_from_db()
        fecha_original = self.turno.fecha_pago
        self.assertIsNotNone(fecha_original)

        response = self.client.post(
            self.url,
            self.datos_pago(FormaPago.TRANSFERENCIA, '15000'),
        )
        self.assertEqual(response.status_code, 302)

        self.turno.refresh_from_db()
        self.assertEqual(self.turno.forma_pago, FormaPago.TRANSFERENCIA)
        self.assertEqual(self.turno.monto, Decimal('15000.00'))
        self.assertEqual(self.turno.fecha_pago, fecha_original)
        self.assertEqual(self.turno.pago_registrado_por, self.recepcion)

        log = LogAcceso.objects.filter(
            modelo='Turno',
            objeto_id=self.turno.pk,
            detalle__contains='Pago corregido',
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.usuario, self.recepcion)
        self.assertEqual(log.accion, 'editar')
        self.assertIn('Anterior: Efectivo $12.000', log.detalle)
        self.assertIn('Nuevo: Transferencia $15.000', log.detalle)

    def test_alta_de_pago_tambien_queda_en_auditoria(self):
        self.client.post(self.url, self.datos_pago(FormaPago.EFECTIVO, '9000'))
        log = LogAcceso.objects.filter(
            modelo='Turno',
            objeto_id=self.turno.pk,
            detalle__contains='Pago registrado',
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.accion, 'crear')
        self.assertIn('Efectivo $9.000', log.detalle)


class CajaDashboardTests(BasePagosTests):
    def setUp(self):
        self.login(self.recepcion)

    def test_totales_de_caja_y_cambio_de_dia(self):
        dia = date(2026, 11, 10)
        dia_siguiente = date(2026, 11, 11)
        tz = ZoneInfo(TZ_BUENOS_AIRES)

        self.crear_turno_pagado(
            datetime.combine(dia, time(10, 0), tzinfo=tz),
            FormaPago.EFECTIVO,
            Decimal('10000.00'),
        )
        self.crear_turno_pagado(
            datetime.combine(dia, time(11, 30), tzinfo=tz),
            FormaPago.TRANSFERENCIA,
            Decimal('25000.50'),
        )
        self.crear_turno_pagado(
            datetime.combine(dia, time(12, 0), tzinfo=tz),
            FormaPago.COBERTURA,
            None,
        )
        self.crear_turno_pagado(
            datetime.combine(dia_siguiente, time(9, 0), tzinfo=tz),
            FormaPago.EFECTIVO,
            Decimal('5000.00'),
        )

        with override_settings(TIME_ZONE=TZ_BUENOS_AIRES):
            response = self.client.get(
                reverse('dashboard:index'),
                {'fecha_caja': dia.isoformat()},
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                response.context['caja']['efectivo'],
                Decimal('10000.00'),
            )
            self.assertEqual(
                response.context['caja']['transferencia'],
                Decimal('25000.50'),
            )
            self.assertEqual(
                response.context['caja']['general'],
                Decimal('35000.50'),
            )
            self.assertEqual(response.context['caja']['cantidad'], 2)
            self.assertContains(response, '$10.000')
            self.assertContains(response, '$25.000,50')
            self.assertContains(response, '$35.000,50')

            response = self.client.get(
                reverse('dashboard:index'),
                {'fecha_caja': dia_siguiente.isoformat()},
            )
            self.assertEqual(
                response.context['caja']['general'],
                Decimal('5000.00'),
            )
            self.assertEqual(response.context['caja']['cantidad'], 1)

    def test_caja_respeta_la_zona_horaria_del_proyecto(self):
        # 02:00 UTC del 1/11 es 23:00 del 31/10 en Buenos Aires.
        self.crear_turno_pagado(
            datetime(2026, 11, 1, 2, 0, tzinfo=ZoneInfo('UTC')),
            FormaPago.EFECTIVO,
            Decimal('7000.00'),
        )

        with override_settings(TIME_ZONE=TZ_BUENOS_AIRES):
            response = self.client.get(
                reverse('dashboard:index'),
                {'fecha_caja': '2026-10-31'},
            )
            self.assertEqual(
                response.context['caja']['general'],
                Decimal('7000.00'),
            )

            response = self.client.get(
                reverse('dashboard:index'),
                {'fecha_caja': '2026-11-01'},
            )
            self.assertEqual(
                response.context['caja']['general'],
                Decimal('0.00'),
            )
            self.assertEqual(response.context['caja']['cantidad'], 0)

    def test_fecha_por_defecto_es_hoy(self):
        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response.context['caja_fecha'], timezone.localdate())


class OcultamientoPagosTests(BasePagosTests):
    def setUp(self):
        self.turno.forma_pago = FormaPago.EFECTIVO
        self.turno.monto = Decimal('12345.00')
        self.turno.fecha_pago = timezone.now()
        self.turno.pago_registrado_por = self.recepcion
        self.turno.save()

    def test_profesional_no_ve_montos_ni_formas_de_pago(self):
        self.login(self.user_profesional)
        response = self.client.get(
            reverse('turnos:agenda'),
            {'fecha': date.today().isoformat()},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '12.345')
        self.assertNotContains(response, 'Efectivo')
        self.assertNotContains(
            response,
            reverse('turnos:registrar_pago', args=[self.turno.pk]),
        )
        self.assertNotContains(response, 'Registrar pago')

    @override_settings(PAGOS_VISIBLES_PARA_PROFESIONAL=True)
    def test_profesional_ve_montos_si_el_setting_esta_activo(self):
        self.login(self.user_profesional)
        response = self.client.get(
            reverse('turnos:agenda'),
            {'fecha': date.today().isoformat()},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '12.345')
        self.assertContains(response, 'Efectivo')
        self.assertNotContains(
            response,
            reverse('turnos:registrar_pago', args=[self.turno.pk]),
        )

    def test_profesional_no_ve_la_caja_en_el_dashboard(self):
        self.login(self.user_profesional)
        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Caja del día')
        self.assertNotContains(response, '12.345')

    def test_recepcion_ve_la_insignia_y_el_boton_de_pago(self):
        self.login(self.recepcion)
        response = self.client.get(
            reverse('turnos:agenda'),
            {'fecha': date.today().isoformat()},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Efectivo $12.345')
        self.assertContains(
            response,
            reverse('turnos:registrar_pago', args=[self.turno.pk]),
        )
        self.assertContains(response, 'Corregir pago')


class CsvPagosTests(BasePagosTests):
    def test_csv_incluye_columnas_de_pago(self):
        self.turno.forma_pago = FormaPago.TRANSFERENCIA
        self.turno.monto = Decimal('15000.00')
        self.turno.fecha_pago = timezone.now()
        self.turno.pago_registrado_por = self.recepcion
        self.turno.save()

        self.login(self.recepcion)
        response = self.client.get(
            reverse('turnos:exportar_csv'),
            {'fecha': date.today().isoformat()},
        )
        contenido = response.content.decode('utf-8-sig')
        self.assertIn('Forma de pago', contenido)
        self.assertIn('Monto', contenido)
        self.assertIn('Fecha de pago', contenido)
        self.assertIn('Pago registrado por', contenido)
        self.assertIn('Transferencia', contenido)
        self.assertIn('15000.00', contenido)
        self.assertIn(self.recepcion.username, contenido)

    def test_profesional_no_puede_exportar(self):
        self.login(self.user_profesional)
        response = self.client.get(reverse('turnos:exportar_csv'))
        self.assertEqual(response.status_code, 403)

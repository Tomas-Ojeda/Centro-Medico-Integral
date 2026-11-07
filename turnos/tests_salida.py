from datetime import timedelta
from urllib.parse import parse_qs, urlparse

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from auditoria.models import LogAcceso
from turnos.models import EstadoTurno, MotivoSalida, Turno

from .tests_llegada import BaseLlegadaTests


class BaseSalidaTests(BaseLlegadaTests):
    def url_salida(self, turno):
        return reverse('turnos:salida', args=[turno.pk])

    def url_volvio(self, turno):
        return reverse('turnos:volvio', args=[turno.pk])

    def salir(self, turno, motivo, **extra):
        datos = {'motivo': motivo}
        datos.update(extra)
        return self.client.post(self.url_salida(turno), datos)


class SalidaPermisosTests(BaseSalidaTests):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.recepcion)

    def test_recepcion_marca_atendiendo(self):
        self.marcar_llegada(self.turno)

        response = self.salir(self.turno, MotivoSalida.ATENDIENDO)

        self.assertEqual(response.status_code, 302)
        self.turno.refresh_from_db()
        self.assertIsNotNone(self.turno.hora_salida)
        self.assertEqual(self.turno.motivo_salida, MotivoSalida.ATENDIENDO)
        self.assertEqual(self.turno.salida_marcada_por, self.recepcion)
        self.assertFalse(self.turno.en_sala_espera)

        log = LogAcceso.objects.filter(
            modelo='Turno',
            objeto_id=self.turno.pk,
            accion='editar',
            detalle__contains='Salida de la sala',
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.usuario, self.recepcion)
        self.assertIn('Pasó a consultorio', log.detalle)
        self.assertIn(
            timezone.localtime(self.turno.hora_salida).strftime('%H:%M'),
            log.detalle,
        )

    def test_recepcion_marca_retirado(self):
        self.marcar_llegada(self.turno)

        response = self.salir(self.turno, MotivoSalida.RETIRADO)

        self.assertEqual(response.status_code, 302)
        self.turno.refresh_from_db()
        self.assertEqual(self.turno.motivo_salida, MotivoSalida.RETIRADO)
        self.assertEqual(self.turno.salida_marcada_por, self.recepcion)

        log = LogAcceso.objects.filter(
            modelo='Turno',
            objeto_id=self.turno.pk,
            detalle__contains='Salida de la sala',
        ).first()
        self.assertIsNotNone(log)
        self.assertIn('Se retiró', log.detalle)

    def test_admin_puede_marcar_retirado(self):
        self.marcar_llegada(self.turno)
        self.client.force_login(self.admin)

        response = self.salir(self.turno, MotivoSalida.RETIRADO)

        self.assertEqual(response.status_code, 302)
        self.turno.refresh_from_db()
        self.assertEqual(self.turno.motivo_salida, MotivoSalida.RETIRADO)
        self.assertEqual(self.turno.salida_marcada_por, self.admin)

    def test_profesional_marca_atendiendo_su_turno(self):
        self.marcar_llegada(self.turno)
        self.client.force_login(self.user_profesional)

        response = self.salir(self.turno, MotivoSalida.ATENDIENDO)

        self.assertEqual(response.status_code, 302)
        self.turno.refresh_from_db()
        self.assertEqual(self.turno.motivo_salida, MotivoSalida.ATENDIENDO)
        self.assertEqual(
            self.turno.salida_marcada_por,
            self.user_profesional,
        )

    def test_profesional_no_puede_marcar_retirado(self):
        self.marcar_llegada(self.turno)
        self.client.force_login(self.user_profesional)

        response = self.salir(self.turno, MotivoSalida.RETIRADO)

        self.assertEqual(response.status_code, 403)
        self.turno.refresh_from_db()
        self.assertIsNone(self.turno.hora_salida)
        self.assertFalse(
            LogAcceso.objects.filter(
                modelo='Turno',
                objeto_id=self.turno.pk,
                detalle__contains='Salida de la sala',
            ).exists()
        )

    def test_profesional_recibe_404_en_turno_ajeno(self):
        turno_ajeno = self.crear_turno(
            paciente=self.otro_paciente,
            profesional=self.otro_profesional,
            hora=11,
        )
        self.marcar_llegada(turno_ajeno)
        self.client.force_login(self.user_profesional)

        response = self.salir(turno_ajeno, MotivoSalida.ATENDIENDO)

        self.assertEqual(response.status_code, 404)
        turno_ajeno.refresh_from_db()
        self.assertIsNone(turno_ajeno.hora_salida)

    @override_settings(PROFESIONAL_PUEDE_LLAMAR_PACIENTE=False)
    def test_profesional_recibe_403_si_el_setting_esta_apagado(self):
        self.marcar_llegada(self.turno)
        self.client.force_login(self.user_profesional)

        response = self.salir(self.turno, MotivoSalida.ATENDIENDO)

        self.assertEqual(response.status_code, 403)
        self.turno.refresh_from_db()
        self.assertIsNone(self.turno.hora_salida)

    def test_usuario_sin_rol_recibe_403(self):
        self.marcar_llegada(self.turno)
        self.client.force_login(self.sin_rol)

        response = self.salir(self.turno, MotivoSalida.ATENDIENDO)

        self.assertEqual(response.status_code, 403)
        self.turno.refresh_from_db()
        self.assertIsNone(self.turno.hora_salida)

    def test_profesional_no_puede_marcar_volvio(self):
        self.marcar_llegada(self.turno)
        self.salir(self.turno, MotivoSalida.ATENDIENDO)
        self.client.force_login(self.user_profesional)

        response = self.client.post(self.url_volvio(self.turno))

        self.assertEqual(response.status_code, 403)
        self.turno.refresh_from_db()
        self.assertIsNotNone(self.turno.hora_salida)


class SalidaValidacionesTests(BaseSalidaTests):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.recepcion)

    def test_no_se_puede_salir_sin_llegada(self):
        response = self.client.post(
            self.url_salida(self.turno),
            {'motivo': MotivoSalida.ATENDIENDO},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'El paciente todavía no llegó a la sala de espera.',
        )
        self.turno.refresh_from_db()
        self.assertIsNone(self.turno.hora_salida)

    def test_no_se_puede_salir_en_otra_fecha(self):
        turno_manana = self.crear_turno(
            fecha=self.hoy + timedelta(days=1),
        )
        self.marcar_llegada(turno_manana)

        response = self.client.post(
            self.url_salida(turno_manana),
            {'motivo': MotivoSalida.ATENDIENDO},
            follow=True,
        )

        self.assertContains(
            response,
            'Solo se puede registrar la salida el día del turno.',
        )
        turno_manana.refresh_from_db()
        self.assertIsNone(turno_manana.hora_salida)

    def test_no_se_puede_salir_en_estados_terminados(self):
        self.marcar_llegada(self.turno)

        for estado in (
            EstadoTurno.REALIZADO,
            EstadoTurno.CANCELADO,
            EstadoTurno.AUSENTE,
        ):
            with self.subTest(estado=estado):
                Turno.objects.filter(pk=self.turno.pk).update(estado=estado)
                response = self.client.post(
                    self.url_salida(self.turno),
                    {'motivo': MotivoSalida.ATENDIENDO},
                    follow=True,
                )
                self.assertContains(
                    response,
                    'Solo se puede registrar la salida de turnos pendientes '
                    'o confirmados.',
                )
                self.turno.refresh_from_db()
                self.assertIsNone(self.turno.hora_salida)

    def test_no_se_puede_salir_dos_veces(self):
        self.marcar_llegada(self.turno)
        self.salir(self.turno, MotivoSalida.ATENDIENDO)
        self.turno.refresh_from_db()
        hora_salida = self.turno.hora_salida

        response = self.client.post(
            self.url_salida(self.turno),
            {'motivo': MotivoSalida.RETIRADO},
            follow=True,
        )

        self.assertContains(
            response,
            'El paciente ya había salido de la sala de espera.',
        )
        self.turno.refresh_from_db()
        self.assertEqual(self.turno.hora_salida, hora_salida)
        self.assertEqual(self.turno.motivo_salida, MotivoSalida.ATENDIENDO)

    def test_motivo_invalido_no_registra_salida(self):
        self.marcar_llegada(self.turno)

        response = self.client.post(
            self.url_salida(self.turno),
            {'motivo': 'otro'},
            follow=True,
        )

        self.assertContains(
            response,
            'El motivo de salida indicado no es válido.',
        )
        self.turno.refresh_from_db()
        self.assertIsNone(self.turno.hora_salida)

    def test_no_se_puede_volver_sin_haber_salido(self):
        self.marcar_llegada(self.turno)

        response = self.client.post(
            self.url_volvio(self.turno),
            follow=True,
        )

        self.assertContains(
            response,
            'El paciente no había salido de la sala de espera.',
        )
        self.turno.refresh_from_db()
        self.assertIsNotNone(self.turno.hora_llegada)


class SalidaColaTests(BaseSalidaTests):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.recepcion)

    def test_quien_sale_deja_de_aparecer_en_panel_json_y_contador(self):
        self.marcar_llegada(self.turno)

        agenda = self.client.get(
            reverse('turnos:agenda'),
            {'fecha': self.hoy.isoformat()},
        )
        self.assertEqual(agenda.context['total_sala'], 1)

        json_inicial = self.client.get(
            reverse('turnos:sala_espera'),
            {'fecha': self.hoy.isoformat()},
        ).json()
        self.assertEqual(json_inicial['total'], 1)
        item = json_inicial['cola'][0]
        self.assertTrue(item['puede_llamar'])
        self.assertTrue(item['puede_sacar'])
        self.assertIn('salida_url', item)

        self.salir(self.turno, MotivoSalida.ATENDIENDO)
        self.turno.refresh_from_db()
        hora_salida = timezone.localtime(
            self.turno.hora_salida
        ).strftime('%H:%M')

        agenda = self.client.get(
            reverse('turnos:agenda'),
            {'fecha': self.hoy.isoformat()},
        )
        self.assertEqual(agenda.context['total_sala'], 0)
        self.assertEqual(agenda.context['grupos_sala'], [])
        self.assertContains(agenda, 'Nadie en sala de espera')
        self.assertContains(agenda, f'En consultorio desde {hora_salida}')

        data = self.client.get(
            reverse('turnos:sala_espera'),
            {'fecha': self.hoy.isoformat()},
        ).json()
        self.assertEqual(data['total'], 0)
        self.assertEqual(data['cola'], [])
        self.assertEqual(
            data['salidas'][str(self.turno.pk)]['motivo'],
            MotivoSalida.ATENDIENDO,
        )

        dashboard = self.client.get(reverse('dashboard:index'))
        self.assertEqual(dashboard.context['en_sala_espera'], 0)
        self.assertContains(dashboard, 'En consultorio')

    def test_etiqueta_de_retirado(self):
        self.marcar_llegada(self.turno)
        self.salir(self.turno, MotivoSalida.RETIRADO)
        self.turno.refresh_from_db()
        hora_salida = timezone.localtime(
            self.turno.hora_salida
        ).strftime('%H:%M')

        response = self.client.get(
            reverse('turnos:agenda'),
            {'fecha': self.hoy.isoformat()},
        )

        self.assertContains(
            response,
            f'Salió de la sala · {hora_salida} (se retiró)',
        )

    def test_panel_muestra_acciones_segun_rol(self):
        self.marcar_llegada(self.turno)

        response = self.client.get(
            reverse('turnos:agenda'),
            {'fecha': self.hoy.isoformat()},
        )
        self.assertContains(response, 'data-motivo="atendiendo"')
        self.assertContains(response, 'data-motivo="retirado"')
        self.assertContains(response, 'js-form-salida')

        self.client.force_login(self.user_profesional)
        response = self.client.get(
            reverse('turnos:agenda'),
            {'fecha': self.hoy.isoformat()},
        )
        self.assertContains(response, 'data-motivo="atendiendo"')
        self.assertNotContains(response, 'data-motivo="retirado"')

    @override_settings(PROFESIONAL_PUEDE_LLAMAR_PACIENTE=False)
    def test_panel_profesional_sin_permiso_no_muestra_acciones(self):
        self.marcar_llegada(self.turno)
        self.client.force_login(self.user_profesional)

        response = self.client.get(
            reverse('turnos:agenda'),
            {'fecha': self.hoy.isoformat()},
        )
        self.assertNotContains(response, 'data-motivo="atendiendo"')

        data = self.client.get(
            reverse('turnos:sala_espera'),
            {'fecha': self.hoy.isoformat()},
        ).json()
        item = data['cola'][0]
        self.assertFalse(item['puede_llamar'])
        self.assertFalse(item['puede_sacar'])

    def test_json_profesional_solo_puede_llamar(self):
        self.marcar_llegada(self.turno)
        self.client.force_login(self.user_profesional)

        data = self.client.get(
            reverse('turnos:sala_espera'),
            {'fecha': self.hoy.isoformat()},
        ).json()

        item = data['cola'][0]
        self.assertTrue(item['puede_llamar'])
        self.assertFalse(item['puede_sacar'])

    def test_volvio_devuelve_al_final_de_la_cola(self):
        turno_segundo = self.crear_turno(hora=11)
        self.marcar_llegada(self.turno, minutos_atras=20)
        self.marcar_llegada(turno_segundo, minutos_atras=5)
        self.salir(self.turno, MotivoSalida.ATENDIENDO)

        response = self.client.post(self.url_volvio(self.turno))

        self.assertEqual(response.status_code, 302)
        self.turno.refresh_from_db()
        turno_segundo.refresh_from_db()
        self.assertIsNone(self.turno.hora_salida)
        self.assertEqual(self.turno.motivo_salida, '')
        self.assertIsNone(self.turno.salida_marcada_por)
        self.assertGreater(
            self.turno.hora_llegada,
            turno_segundo.hora_llegada,
        )
        self.assertTrue(self.turno.en_sala_espera)

        data = self.client.get(
            reverse('turnos:sala_espera'),
            {'fecha': self.hoy.isoformat()},
        ).json()
        self.assertEqual(data['total'], 2)
        self.assertEqual(
            [item['id'] for item in data['cola']],
            [turno_segundo.pk, self.turno.pk],
        )

        log = LogAcceso.objects.filter(
            modelo='Turno',
            objeto_id=self.turno.pk,
            detalle__contains='Volvió a la sala',
        ).first()
        self.assertIsNotNone(log)
        self.assertIn('Llegada anterior', log.detalle)
        self.assertEqual(log.usuario, self.recepcion)

    def test_deshacer_llegada_limpia_llegada_y_salida(self):
        self.marcar_llegada(self.turno)
        self.salir(self.turno, MotivoSalida.RETIRADO)

        response = self.client.post(self.url_llegada(self.turno))

        self.assertEqual(response.status_code, 302)
        self.turno.refresh_from_db()
        self.assertIsNone(self.turno.hora_llegada)
        self.assertIsNone(self.turno.llegada_marcada_por)
        self.assertIsNone(self.turno.hora_salida)
        self.assertEqual(self.turno.motivo_salida, '')
        self.assertIsNone(self.turno.salida_marcada_por)
        self.assertFalse(self.turno.en_sala_espera)

        self.assertTrue(
            LogAcceso.objects.filter(
                modelo='Turno',
                objeto_id=self.turno.pk,
                detalle__contains='Llegada deshecha',
            ).exists()
        )


class SalidaRetornoFiltrosTests(BaseSalidaTests):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.recepcion)

    def test_salida_conserva_fecha_y_filtros_con_next(self):
        self.marcar_llegada(self.turno)
        destino = self.url_agenda(
            fecha=self.hoy.isoformat(),
            q='Fern',
            especialidad='Cardiología',
            orden='llegada',
        )

        response = self.salir(
            self.turno,
            MotivoSalida.ATENDIENDO,
            next=destino,
        )

        self.assertRedirects(
            response,
            destino,
            fetch_redirect_response=False,
        )

    def test_volvio_conserva_fecha_y_filtros_con_next(self):
        self.marcar_llegada(self.turno)
        self.salir(self.turno, MotivoSalida.ATENDIENDO)
        destino = self.url_agenda(
            fecha=self.hoy.isoformat(),
            q='Fern',
            orden='llegada',
        )

        response = self.client.post(
            self.url_volvio(self.turno),
            {'next': destino},
        )

        self.assertRedirects(
            response,
            destino,
            fetch_redirect_response=False,
        )

    def test_salida_sin_next_vuelve_a_la_agenda_con_filtros_del_post(self):
        self.marcar_llegada(self.turno)

        response = self.client.post(
            self.url_salida(self.turno),
            {
                'motivo': MotivoSalida.ATENDIENDO,
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

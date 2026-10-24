import json
import tempfile
from datetime import date, time

from django.contrib.auth.models import Group, User
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from historias.models import Consulta
from pacientes.models import Paciente
from profesionales.models import Profesional
from turnos.models import Turno

from consultorio_salto.permisos import (
    GRUPO_PROFESIONAL,
    GRUPO_RECEPCION,
    es_profesional,
    es_recepcion,
)


CLAVE = 'ClaveSegura2026!'


class BaseRolesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.grupo_recepcion, _ = Group.objects.get_or_create(
            name=GRUPO_RECEPCION
        )
        cls.grupo_profesional, _ = Group.objects.get_or_create(
            name=GRUPO_PROFESIONAL
        )

        cls.recepcion = User.objects.create_user(
            username='recepcion_test',
            password=CLAVE,
        )
        cls.recepcion.groups.add(cls.grupo_recepcion)

        cls.admin = User.objects.create_superuser(
            username='admin_test',
            email='admin@example.com',
            password=CLAVE,
        )

        cls.user_a = User.objects.create_user(
            username='prof_ana',
            password=CLAVE,
        )
        cls.user_a.groups.add(cls.grupo_profesional)

        cls.user_b = User.objects.create_user(
            username='prof_bruno',
            password=CLAVE,
        )
        cls.user_b.groups.add(cls.grupo_profesional)

        cls.prof_a = Profesional.objects.create(
            nombre='Ana',
            apellido='García',
            dni='30000001',
            email='ana.garcia@example.com',
            fecha_ingreso=date(2020, 1, 15),
            usuario=cls.user_a,
        )
        cls.prof_b = Profesional.objects.create(
            nombre='Bruno',
            apellido='Pérez',
            dni='30000002',
            email='bruno.perez@example.com',
            fecha_ingreso=date(2021, 2, 20),
            usuario=cls.user_b,
        )

        cls.p1 = Paciente.objects.create(
            dni='31000001',
            nombre='Paciente',
            apellido='Alfa',
            fecha_nacimiento=date(1985, 4, 12),
        )
        cls.p2 = Paciente.objects.create(
            dni='31000002',
            nombre='Paciente',
            apellido='Beta',
            fecha_nacimiento=date(1990, 6, 20),
        )
        cls.p3 = Paciente.objects.create(
            dni='31000003',
            nombre='Paciente',
            apellido='Gamma',
            fecha_nacimiento=date(1978, 9, 3),
        )
        cls.p4 = Paciente.objects.create(
            dni='31000004',
            nombre='Paciente',
            apellido='Delta',
            fecha_nacimiento=date(2000, 1, 1),
        )

        hoy = date.today()
        cls.fecha_hora = timezone.make_aware(
            timezone.datetime.combine(hoy, time(10, 0))
        )
        cls.fecha_hora_b = timezone.make_aware(
            timezone.datetime.combine(hoy, time(11, 0))
        )

        # P1: atendido por A (turno) y por B (consulta).
        cls.turno_a = Turno.objects.create(
            paciente=cls.p1,
            profesional=cls.prof_a,
            fecha_hora=cls.fecha_hora,
            motivo='Control A',
        )
        cls.turno_b = Turno.objects.create(
            paciente=cls.p2,
            profesional=cls.prof_b,
            fecha_hora=cls.fecha_hora_b,
            motivo='Control B',
        )

        cls.consulta_a = Consulta.objects.create(
            paciente=cls.p1,
            profesional=cls.prof_a,
            fecha_hora=cls.fecha_hora,
            diagnostico='Diagnóstico A',
        )
        cls.consulta_b = Consulta.objects.create(
            paciente=cls.p1,
            profesional=cls.prof_b,
            fecha_hora=cls.fecha_hora_b,
            diagnostico='Diagnóstico B',
        )
        cls.consulta_b2 = Consulta.objects.create(
            paciente=cls.p2,
            profesional=cls.prof_b,
            fecha_hora=cls.fecha_hora_b,
            diagnostico='Diagnóstico B2',
        )
        # P4: atendido por A solamente mediante consulta.
        cls.consulta_a4 = Consulta.objects.create(
            paciente=cls.p4,
            profesional=cls.prof_a,
            fecha_hora=cls.fecha_hora,
            diagnostico='Diagnóstico A4',
        )

    def login(self, user):
        self.client.force_login(user)


class RolesHelpersTests(BaseRolesTests):
    def test_grupos_creados(self):
        self.assertTrue(Group.objects.filter(name=GRUPO_RECEPCION).exists())
        self.assertTrue(Group.objects.filter(name=GRUPO_PROFESIONAL).exists())

    def test_roles_efectivos(self):
        self.assertTrue(es_recepcion(self.admin))
        self.assertTrue(es_recepcion(self.recepcion))
        self.assertFalse(es_profesional(self.recepcion))
        self.assertTrue(es_profesional(self.user_a))
        self.assertFalse(es_recepcion(self.user_a))

    def test_atendidos_por_incluye_turnos_y_consultas(self):
        atendidos = list(
            Paciente.objects.atendidos_por(self.prof_a).values_list(
                'pk', flat=True
            )
        )
        self.assertCountEqual(atendidos, [self.p1.pk, self.p4.pk])


class MatrizRolesTests(BaseRolesTests):
    def test_anonimo_redirige_al_login(self):
        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_usuario_sin_grupo_recibe_403_en_toda_la_app(self):
        user = User.objects.create_user(
            username='sin_rol',
            password=CLAVE,
        )
        self.login(user)
        urls = [
            reverse('dashboard:index'),
            reverse('pacientes:lista'),
            reverse('pacientes:detalle', args=[self.p1.pk]),
            reverse('turnos:agenda'),
            reverse('profesionales:lista'),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_recepcion_accede_a_todas_las_secciones(self):
        self.login(self.recepcion)
        urls = [
            reverse('dashboard:index'),
            reverse('pacientes:lista'),
            reverse('pacientes:detalle', args=[self.p3.pk]),
            reverse('turnos:agenda'),
            reverse('profesionales:lista'),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_administrador_accede_a_todas_las_secciones(self):
        self.login(self.admin)
        urls = [
            reverse('dashboard:index'),
            reverse('pacientes:lista'),
            reverse('pacientes:detalle', args=[self.p3.pk]),
            reverse('turnos:agenda'),
            reverse('profesionales:lista'),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_etiqueta_de_rol_en_sidebar(self):
        self.login(self.user_a)
        response = self.client.get(reverse('dashboard:index'))
        self.assertContains(response, '>Profesional<')
        self.assertNotContains(response, reverse('profesionales:lista'))

    def test_admin_de_django_solo_para_superusuarios(self):
        self.login(self.recepcion)
        self.assertEqual(
            self.client.get(reverse('admin:index')).status_code,
            403,
        )
        self.login(self.user_a)
        self.assertEqual(
            self.client.get(reverse('admin:index')).status_code,
            403,
        )
        self.login(self.admin)
        self.assertEqual(
            self.client.get(reverse('admin:index')).status_code,
            200,
        )


class ProfesionalPacientesTests(BaseRolesTests):
    def setUp(self):
        self.login(self.user_a)

    def test_lista_solo_muestra_pacientes_atendidos(self):
        response = self.client.get(reverse('pacientes:lista'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.p1.apellido)
        self.assertContains(response, self.p4.apellido)
        self.assertNotContains(response, self.p2.apellido)
        self.assertNotContains(response, self.p3.apellido)

    def test_detalle_propio_y_ajeno(self):
        self.assertEqual(
            self.client.get(
                reverse('pacientes:detalle', args=[self.p1.pk])
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                reverse('pacientes:detalle', args=[self.p2.pk])
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                reverse('pacientes:detalle', args=[self.p3.pk])
            ).status_code,
            404,
        )

    def test_detalle_oculta_acciones_de_paciente(self):
        response = self.client.get(
            reverse('pacientes:detalle', args=[self.p1.pk])
        )
        self.assertContains(
            response,
            reverse('pacientes:descargar_pdf', args=[self.p1.pk]),
        )
        self.assertContains(
            response,
            reverse('historias:nueva_consulta', args=[self.p1.pk]),
        )
        self.assertNotContains(response, reverse('pacientes:crear'))
        self.assertNotContains(response, reverse('pacientes:importar'))
        self.assertNotContains(
            response,
            reverse('pacientes:editar', args=[self.p1.pk]),
        )
        self.assertNotContains(
            response,
            reverse('pacientes:eliminar', args=[self.p1.pk]),
        )

    def test_detalle_permite_editar_solo_sus_consultas(self):
        response = self.client.get(
            reverse('pacientes:detalle', args=[self.p1.pk])
        )
        self.assertContains(
            response,
            reverse('historias:editar_consulta', args=[self.consulta_a.pk]),
        )
        self.assertNotContains(
            response,
            reverse('historias:editar_consulta', args=[self.consulta_b.pk]),
        )
        self.assertNotContains(
            response,
            reverse('historias:eliminar_consulta', args=[self.consulta_a.pk]),
        )

    def test_no_puede_crear_editar_eliminar_ni_importar_pacientes(self):
        self.assertEqual(
            self.client.get(reverse('pacientes:crear')).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(reverse('pacientes:crear'), {
                'dni': '31999999',
                'nombre': 'Nuevo',
                'apellido': 'Paciente',
                'fecha_nacimiento': '1990-01-01',
                'obra_social': 'Particular',
            }).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(
                reverse('pacientes:editar', args=[self.p1.pk])
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                reverse('pacientes:eliminar', args=[self.p1.pk])
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(reverse('pacientes:importar')).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                reverse('pacientes:importar'),
                data=json.dumps({}),
                content_type='application/json',
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                reverse('pacientes:guardar_importados'),
                data=json.dumps({'pacientes': []}),
                content_type='application/json',
            ).status_code,
            403,
        )

    def test_pdf_solo_de_pacientes_atendidos(self):
        self.assertEqual(
            self.client.get(
                reverse('pacientes:descargar_pdf', args=[self.p1.pk])
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                reverse('pacientes:descargar_pdf', args=[self.p2.pk])
            ).status_code,
            404,
        )

    def test_adjunto_solo_de_pacientes_atendidos(self):
        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                self.consulta_b2.archivo_adjunto.save(
                    'receta.pdf',
                    ContentFile(b'%PDF-1.4\n'),
                    save=True,
                )
                respuesta_a = self.client.get(
                    reverse(
                        'historias:descargar_adjunto',
                        args=[self.consulta_b2.pk],
                    )
                )
                self.assertEqual(respuesta_a.status_code, 404)

                self.login(self.user_b)
                respuesta_b = self.client.get(
                    reverse(
                        'historias:descargar_adjunto',
                        args=[self.consulta_b2.pk],
                    )
                )
                self.assertEqual(respuesta_b.status_code, 200)
                respuesta_b.close()


class ProfesionalConsultasTests(BaseRolesTests):
    def setUp(self):
        self.login(self.user_a)

    def datos_consulta(self, profesional):
        return {
            'profesional': profesional.pk,
            'fecha_hora': self.fecha_hora.strftime('%Y-%m-%dT%H:%M'),
            'motivo': 'Control',
            'diagnostico': 'Diagnóstico de prueba',
            'evolucion': '',
            'tratamiento': '',
        }

    def test_crea_consulta_solo_para_paciente_atendido(self):
        self.assertEqual(
            self.client.get(
                reverse('historias:nueva_consulta', args=[self.p2.pk])
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                reverse('historias:nueva_consulta', args=[self.p3.pk]),
                self.datos_consulta(self.prof_a),
            ).status_code,
            404,
        )

    def test_crea_consulta_forzando_su_profesional(self):
        response = self.client.post(
            reverse('historias:nueva_consulta', args=[self.p1.pk]),
            self.datos_consulta(self.prof_b),
        )
        self.assertEqual(response.status_code, 302)

        nueva = Consulta.objects.filter(
            paciente=self.p1,
            diagnostico='Diagnóstico de prueba',
        ).get()
        self.assertEqual(nueva.profesional, self.prof_a)

    def test_edita_solo_sus_consultas(self):
        self.assertEqual(
            self.client.get(
                reverse('historias:editar_consulta', args=[self.consulta_a.pk])
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                reverse('historias:editar_consulta', args=[self.consulta_b.pk])
            ).status_code,
            404,
        )

    def test_editar_fuerza_su_profesional(self):
        response = self.client.post(
            reverse('historias:editar_consulta', args=[self.consulta_a.pk]),
            self.datos_consulta(self.prof_b),
        )
        self.assertEqual(response.status_code, 302)
        self.consulta_a.refresh_from_db()
        self.assertEqual(self.consulta_a.profesional, self.prof_a)

    def test_no_puede_eliminar_consultas(self):
        self.assertEqual(
            self.client.post(
                reverse(
                    'historias:eliminar_consulta',
                    args=[self.consulta_a.pk],
                )
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                reverse(
                    'historias:eliminar_consulta',
                    args=[self.consulta_b.pk],
                )
            ).status_code,
            403,
        )


class ProfesionalTurnosTests(BaseRolesTests):
    def setUp(self):
        self.login(self.user_a)

    def test_agenda_muestra_solo_sus_turnos(self):
        response = self.client.get(
            reverse('turnos:agenda'),
            {'fecha': date.today().isoformat()},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.p1.apellido)
        self.assertNotContains(response, self.p2.apellido)
        self.assertNotContains(response, reverse('turnos:crear'))
        self.assertNotContains(response, reverse('turnos:exportar_csv'))
        self.assertContains(response, 'Solo lectura')

    def test_no_puede_crear_editar_eliminar_ni_cambiar_estado(self):
        self.assertEqual(
            self.client.get(reverse('turnos:crear')).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(reverse('turnos:crear'), {
                'paciente': self.p1.pk,
                'profesional': self.prof_a.pk,
                'fecha_hora': self.fecha_hora.strftime('%Y-%m-%dT%H:%M'),
                'motivo': 'Nuevo',
                'estado': 'pendiente',
                'observaciones': '',
            }).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(
                reverse('turnos:editar', args=[self.turno_a.pk])
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                reverse('turnos:eliminar', args=[self.turno_a.pk])
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                reverse(
                    'turnos:cambiar_estado',
                    args=[self.turno_a.pk, 'realizado'],
                )
            ).status_code,
            403,
        )

    def test_no_puede_exportar_ni_usar_buscadores(self):
        self.assertEqual(
            self.client.get(reverse('turnos:exportar_csv')).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(reverse('turnos:buscar_pacientes')).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(reverse('turnos:buscar_profesionales')).status_code,
            403,
        )

    def test_no_puede_acceder_al_turno_de_otro_profesional(self):
        self.assertEqual(
            self.client.get(
                reverse('turnos:editar', args=[self.turno_b.pk])
            ).status_code,
            403,
        )
        response = self.client.get(
            reverse('turnos:agenda'),
            {
                'fecha': date.today().isoformat(),
                'profesional': self.prof_b.pk,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.p2.apellido)


class ProfesionalDashboardTests(BaseRolesTests):
    def test_dashboard_solo_muestra_sus_datos(self):
        self.login(self.user_a)
        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.p1.apellido)
        self.assertNotContains(response, self.p2.apellido)
        self.assertNotContains(response, self.p3.apellido)
        self.assertNotContains(response, 'Profesionales activos')
        self.assertNotContains(response, reverse('pacientes:crear'))
        self.assertNotContains(response, reverse('turnos:crear'))
        self.assertNotContains(response, reverse('profesionales:crear'))

    def test_profesional_sin_vinculo_recibe_mensaje_y_no_ve_datos(self):
        user = User.objects.create_user(
            username='prof_sin_vinculo',
            password=CLAVE,
        )
        user.groups.add(self.grupo_profesional)
        self.login(user)

        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response.status_code, 403)
        self.assertContains(
            response,
            'Tu usuario no está vinculado a un profesional',
            status_code=403,
        )

    def test_profesional_no_accede_a_profesionales(self):
        self.login(self.user_a)
        self.assertEqual(
            self.client.get(reverse('profesionales:lista')).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(reverse('profesionales:crear')).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(
                reverse('profesionales:editar', args=[self.prof_a.pk])
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(
                reverse('profesionales:eliminar', args=[self.prof_a.pk])
            ).status_code,
            403,
        )

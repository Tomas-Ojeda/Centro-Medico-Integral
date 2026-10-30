from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from auditoria.models import LogAcceso
from consultorio_salto.permisos import GRUPO_PROFESIONAL, GRUPO_RECEPCION
from pacientes.models import Paciente
from profesionales.models import Profesional

from .models import (
    CampoAdicional,
    Consulta,
    ValorCampoAdicional,
)


CLAVE = 'ClaveSegura2026!'


class CamposAdicionalesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        grupo_recepcion, _ = Group.objects.get_or_create(name=GRUPO_RECEPCION)
        grupo_profesional, _ = Group.objects.get_or_create(
            name=GRUPO_PROFESIONAL
        )

        cls.recepcion = User.objects.create_user(
            username='recepcion_campos',
            password=CLAVE,
        )
        cls.recepcion.groups.add(grupo_recepcion)

        cls.admin = User.objects.create_superuser(
            username='admin_campos',
            password=CLAVE,
            email='admin@example.com',
        )

        cls.user_a = User.objects.create_user(
            username='prof_campos_a',
            password=CLAVE,
        )
        cls.user_a.groups.add(grupo_profesional)
        cls.user_b = User.objects.create_user(
            username='prof_campos_b',
            password=CLAVE,
        )
        cls.user_b.groups.add(grupo_profesional)

        cls.prof_a = Profesional.objects.create(
            nombre='Ana',
            apellido='Campos',
            dni='33000001',
            fecha_ingreso=date(2020, 1, 1),
            usuario=cls.user_a,
        )
        cls.prof_b = Profesional.objects.create(
            nombre='Beto',
            apellido='Campos',
            dni='33000002',
            fecha_ingreso=date(2020, 1, 1),
            usuario=cls.user_b,
        )

        cls.paciente = Paciente.objects.create(
            dni='33000010',
            nombre='Paciente',
            apellido='Campos',
            fecha_nacimiento=date(1990, 5, 5),
        )

        cls.campo_general = CampoAdicional.objects.create(
            nombre='Alergias',
            tipo='texto',
            activo=True,
        )
        cls.campo_a = CampoAdicional.objects.create(
            nombre='Peso',
            tipo='numero',
            activo=True,
            profesional=cls.prof_a,
        )
        cls.campo_b = CampoAdicional.objects.create(
            nombre='Altura',
            tipo='numero',
            activo=True,
            profesional=cls.prof_b,
        )

        # Relación profesional A ↔ paciente (necesaria para atendidos_por).
        cls.consulta = Consulta.objects.create(
            paciente=cls.paciente,
            profesional=cls.prof_a,
            fecha_hora=timezone.now(),
            diagnostico='Control',
        )

    def login(self, user):
        self.client.force_login(user)

    def url_quitar(self, campo):
        return reverse('historias:quitar_campo_adicional', args=[campo.pk])

    def url_nueva_consulta(self):
        return reverse('historias:nueva_consulta', args=[self.paciente.pk])

    def test_profesional_ve_sus_campos_y_los_generales(self):
        self.login(self.user_a)
        response = self.client.get(self.url_nueva_consulta())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'name="campo_adicional_{self.campo_general.pk}"')
        self.assertContains(response, f'name="campo_adicional_{self.campo_a.pk}"')
        self.assertNotContains(response, f'name="campo_adicional_{self.campo_b.pk}"')

    def test_recepcion_ve_generales_y_los_del_profesional_elegido(self):
        self.login(self.recepcion)

        sin_profesional = self.client.get(self.url_nueva_consulta())
        self.assertContains(sin_profesional, f'name="campo_adicional_{self.campo_general.pk}"')
        self.assertNotContains(sin_profesional, f'name="campo_adicional_{self.campo_a.pk}"')

        con_profesional = self.client.get(
            self.url_nueva_consulta() + f'?profesional={self.prof_a.pk}'
        )
        self.assertContains(con_profesional, f'name="campo_adicional_{self.campo_general.pk}"')
        self.assertContains(con_profesional, f'name="campo_adicional_{self.campo_a.pk}"')
        self.assertNotContains(con_profesional, f'name="campo_adicional_{self.campo_b.pk}"')
        self.assertContains(con_profesional, f'value="{self.prof_a.pk}" selected')

    def test_dueno_puede_quitar_su_campo_y_queda_inactivo(self):
        self.login(self.user_a)
        response = self.client.post(self.url_quitar(self.campo_a))

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {'ok': True, 'pk': self.campo_a.pk},
        )
        self.campo_a.refresh_from_db()
        self.assertFalse(self.campo_a.activo)
        self.assertTrue(
            LogAcceso.objects.filter(
                accion='borrar',
                modelo='CampoAdicional',
                objeto_id=self.campo_a.pk,
            ).exists()
        )

    def test_profesional_ajeno_no_puede_quitar(self):
        self.login(self.user_b)
        response = self.client.post(self.url_quitar(self.campo_a))

        self.assertEqual(response.status_code, 403)
        self.campo_a.refresh_from_db()
        self.assertTrue(self.campo_a.activo)

    def test_recepcion_no_puede_quitar_campos(self):
        self.login(self.recepcion)

        for campo in (self.campo_a, self.campo_general):
            response = self.client.post(self.url_quitar(campo))
            self.assertEqual(response.status_code, 403)
            campo.refresh_from_db()
            self.assertTrue(campo.activo)

    def test_admin_puede_quitar_campos_generales_y_ajenos(self):
        self.login(self.admin)

        self.assertEqual(
            self.client.post(self.url_quitar(self.campo_general)).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(self.url_quitar(self.campo_b)).status_code,
            200,
        )

        self.campo_general.refresh_from_db()
        self.campo_b.refresh_from_db()
        self.assertFalse(self.campo_general.activo)
        self.assertFalse(self.campo_b.activo)

    def test_quitar_conserva_los_valores_historicos_y_los_muestra(self):
        valor = ValorCampoAdicional.objects.create(
            consulta=self.consulta,
            campo=self.campo_a,
            valor='78.5',
        )
        self.login(self.user_a)

        self.client.post(self.url_quitar(self.campo_a))

        self.assertTrue(
            ValorCampoAdicional.objects.filter(pk=valor.pk).exists()
        )

        detalle = self.client.get(
            reverse('pacientes:detalle', args=[self.paciente.pk])
        )
        self.assertContains(detalle, 'Peso')
        self.assertContains(detalle, '78.5')

        edicion = self.client.get(
            reverse('historias:editar_consulta', args=[self.consulta.pk])
        )
        self.assertContains(edicion, 'Campo inactivo')
        self.assertContains(edicion, '78.5')

    def test_editar_consulta_no_borra_valores_de_campo_quitado(self):
        valor = ValorCampoAdicional.objects.create(
            consulta=self.consulta,
            campo=self.campo_a,
            valor='80',
        )
        self.login(self.user_a)
        self.client.post(self.url_quitar(self.campo_a))

        response = self.client.post(
            reverse('historias:editar_consulta', args=[self.consulta.pk]),
            {
                'fecha_hora': timezone.localtime(
                    self.consulta.fecha_hora
                ).strftime('%Y-%m-%dT%H:%M'),
                'motivo': '',
                'diagnostico': 'Control actualizado',
                'evolucion': '',
                'tratamiento': '',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            ValorCampoAdicional.objects.filter(pk=valor.pk).exists()
        )

    def test_pdf_muestra_valor_de_campo_inactivo(self):
        ValorCampoAdicional.objects.create(
            consulta=self.consulta,
            campo=self.campo_a,
            valor='82',
        )
        self.login(self.user_a)
        self.client.post(self.url_quitar(self.campo_a))

        with patch('pacientes.views.SimpleDocTemplate'), \
                patch('pacientes.views.Paragraph') as mock_paragraph:
            response = self.client.get(
                reverse('pacientes:descargar_pdf', args=[self.paciente.pk])
            )

        self.assertEqual(response.status_code, 200)
        textos = [llamada[0][0] for llamada in mock_paragraph.call_args_list]
        self.assertTrue(
            any('Peso' in texto and '82' in texto for texto in textos)
        )

    def test_dos_profesionales_pueden_tener_campos_con_el_mismo_nombre(self):
        campo_b = CampoAdicional.objects.create(
            nombre='Peso',
            tipo='numero',
            activo=True,
            profesional=self.prof_b,
        )
        self.assertEqual(
            CampoAdicional.objects.filter(nombre='Peso').count(),
            2,
        )

        self.login(self.user_a)
        response = self.client.post(
            self.url_nueva_consulta(),
            {
                'fecha_hora': timezone.localtime(
                    timezone.now()
                ).strftime('%Y-%m-%dT%H:%M'),
                'motivo': '',
                'diagnostico': 'Control con campo nuevo',
                'evolucion': '',
                'tratamiento': '',
                'campo_dinamico_1_nombre': 'Peso',
                'campo_dinamico_1_tipo': 'numero',
                'campo_dinamico_1_valor': '75',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            CampoAdicional.objects.filter(nombre='Peso').count(),
            2,
        )
        valor = ValorCampoAdicional.objects.get(
            consulta__diagnostico='Control con campo nuevo'
        )
        self.assertEqual(valor.campo_id, self.campo_a.pk)
        self.assertNotEqual(valor.campo_id, campo_b.pk)

    def test_recepcion_crea_campos_generales(self):
        self.login(self.recepcion)
        response = self.client.post(
            self.url_nueva_consulta(),
            {
                'profesional': self.prof_a.pk,
                'fecha_hora': timezone.localtime(
                    timezone.now()
                ).strftime('%Y-%m-%dT%H:%M'),
                'motivo': '',
                'diagnostico': 'Control con campo de recepción',
                'evolucion': '',
                'tratamiento': '',
                'campo_dinamico_1_nombre': 'Temperatura',
                'campo_dinamico_1_tipo': 'numero',
                'campo_dinamico_1_valor': '36.5',
            },
        )

        self.assertEqual(response.status_code, 302)
        campo = CampoAdicional.objects.get(nombre='Temperatura')
        self.assertIsNone(campo.profesional)

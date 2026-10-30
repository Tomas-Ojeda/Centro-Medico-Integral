from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from auditoria.models import LogAcceso
from consultorio_salto.permisos import GRUPO_PROFESIONAL, GRUPO_RECEPCION
from pacientes.models import Paciente
from profesionales.models import Profesional

from .models import Consulta, NotaClinica


CLAVE = 'ClaveSegura2026!'
TEXTO_NOTA = 'Paciente refiere mejoría del dolor.'


class NotasClinicasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        grupo_recepcion, _ = Group.objects.get_or_create(name=GRUPO_RECEPCION)
        grupo_profesional, _ = Group.objects.get_or_create(
            name=GRUPO_PROFESIONAL
        )

        cls.recepcion = User.objects.create_user(
            username='recepcion_notas',
            password=CLAVE,
        )
        cls.recepcion.groups.add(grupo_recepcion)

        cls.admin = User.objects.create_superuser(
            username='admin_notas',
            password=CLAVE,
            email='admin_notas@example.com',
        )

        cls.user_a = User.objects.create_user(
            username='prof_notas_a',
            password=CLAVE,
        )
        cls.user_a.groups.add(grupo_profesional)
        cls.user_b = User.objects.create_user(
            username='prof_notas_b',
            password=CLAVE,
        )
        cls.user_b.groups.add(grupo_profesional)

        cls.prof_a = Profesional.objects.create(
            nombre='Ana',
            apellido='Notas',
            dni='34000001',
            fecha_ingreso=date(2020, 1, 1),
            usuario=cls.user_a,
        )
        cls.prof_b = Profesional.objects.create(
            nombre='Beto',
            apellido='Notas',
            dni='34000002',
            fecha_ingreso=date(2020, 1, 1),
            usuario=cls.user_b,
        )

        cls.paciente = Paciente.objects.create(
            dni='34000010',
            nombre='Paciente',
            apellido='Notas',
            fecha_nacimiento=date(1990, 5, 5),
        )
        cls.otro_paciente = Paciente.objects.create(
            dni='34000011',
            nombre='Otro',
            apellido='Paciente',
            fecha_nacimiento=date(1991, 6, 6),
        )

        # El profesional A atiende al paciente.
        Consulta.objects.create(
            paciente=cls.paciente,
            profesional=cls.prof_a,
            fecha_hora=timezone.now(),
            diagnostico='Control',
        )

        cls.nota = NotaClinica.objects.create(
            paciente=cls.paciente,
            autor=cls.user_a,
            texto=TEXTO_NOTA,
        )

    def login(self, user):
        self.client.force_login(user)

    def url_crear(self, paciente=None):
        return reverse(
            'historias:nueva_nota',
            args=[(paciente or self.paciente).pk],
        )

    def url_editar(self, nota=None):
        return reverse(
            'historias:editar_nota',
            args=[(nota or self.nota).pk],
        )

    def url_eliminar(self, nota=None):
        return reverse(
            'historias:eliminar_nota',
            args=[(nota or self.nota).pk],
        )

    def test_profesional_que_atiende_puede_crear_nota(self):
        self.login(self.user_a)
        response = self.client.post(
            self.url_crear(),
            {'texto': 'Nueva anotación del profesional.'},
        )

        self.assertEqual(response.status_code, 302)
        nota = NotaClinica.objects.get(
            texto='Nueva anotación del profesional.'
        )
        self.assertEqual(nota.autor, self.user_a)
        self.assertEqual(nota.profesional, self.prof_a)
        self.assertTrue(
            LogAcceso.objects.filter(
                accion='crear',
                modelo='NotaClinica',
                objeto_id=nota.pk,
            ).exists()
        )

    def test_admin_puede_crear_nota(self):
        self.login(self.admin)
        response = self.client.post(
            self.url_crear(self.otro_paciente),
            {'texto': 'Anotación del administrador.'},
        )

        self.assertEqual(response.status_code, 302)
        nota = NotaClinica.objects.get(texto='Anotación del administrador.')
        self.assertEqual(nota.autor, self.admin)
        self.assertIsNone(nota.profesional)

    def test_recepcion_no_puede_crear_nota(self):
        self.login(self.recepcion)
        response = self.client.post(
            self.url_crear(),
            {'texto': 'No debería crearse.'},
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            NotaClinica.objects.filter(texto='No debería crearse.').exists()
        )

    def test_profesional_ajeno_no_puede_crear_nota(self):
        self.login(self.user_b)
        response = self.client.post(
            self.url_crear(),
            {'texto': 'No debería crearse.'},
        )

        self.assertEqual(response.status_code, 404)

    def test_autor_puede_editar_su_nota_y_se_marca_editada(self):
        self.login(self.user_a)
        response = self.client.post(
            self.url_editar(),
            {'texto': 'Texto corregido por el autor.'},
        )

        self.assertEqual(response.status_code, 302)
        self.nota.refresh_from_db()
        self.assertEqual(self.nota.texto, 'Texto corregido por el autor.')
        self.assertIsNotNone(self.nota.editado_en)
        self.assertTrue(
            LogAcceso.objects.filter(
                accion='editar',
                modelo='NotaClinica',
                objeto_id=self.nota.pk,
            ).exists()
        )

    def test_otro_profesional_no_puede_editar(self):
        self.login(self.user_b)
        response = self.client.post(
            self.url_editar(),
            {'texto': 'Intento ajeno.'},
        )

        self.assertEqual(response.status_code, 403)
        self.nota.refresh_from_db()
        self.assertEqual(self.nota.texto, TEXTO_NOTA)

    def test_admin_puede_editar_nota_ajena(self):
        self.login(self.admin)
        response = self.client.post(
            self.url_editar(),
            {'texto': 'Corrección del administrador.'},
        )

        self.assertEqual(response.status_code, 302)
        self.nota.refresh_from_db()
        self.assertEqual(self.nota.texto, 'Corrección del administrador.')
        self.assertIsNotNone(self.nota.editado_en)

    def test_solo_admin_puede_borrar_nota(self):
        self.login(self.user_a)
        response = self.client.post(self.url_eliminar())
        self.assertEqual(response.status_code, 403)
        self.assertTrue(NotaClinica.objects.filter(pk=self.nota.pk).exists())

        self.login(self.admin)
        response = self.client.post(self.url_eliminar())
        self.assertEqual(response.status_code, 302)
        self.assertFalse(NotaClinica.objects.filter(pk=self.nota.pk).exists())

    def test_recepcion_ve_las_notas_por_defecto(self):
        self.login(self.recepcion)
        response = self.client.get(
            reverse('pacientes:detalle', args=[self.paciente.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Anotaciones')
        self.assertContains(response, TEXTO_NOTA)

    def test_detalle_muestra_autor_especialidad_y_marca_editada(self):
        self.prof_a.especialidades.create(nombre='Cardiología')
        self.nota.editado_en = timezone.now()
        self.nota.save(update_fields=['editado_en'])

        self.login(self.user_a)
        response = self.client.get(
            reverse('pacientes:detalle', args=[self.paciente.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'prof_notas_a')
        self.assertContains(response, 'Cardiología')
        self.assertContains(response, 'editada')

    @override_settings(NOTAS_VISIBLES_PARA_RECEPCION=False)
    def test_recepcion_no_ve_las_notas_si_el_setting_esta_apagado(self):
        self.login(self.recepcion)
        response = self.client.get(
            reverse('pacientes:detalle', args=[self.paciente.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, TEXTO_NOTA)
        self.assertNotContains(response, 'Anotaciones')

    @override_settings(NOTAS_VISIBLES_PARA_RECEPCION=False)
    def test_pdf_no_incluye_notas_para_recepcion_si_el_setting_esta_apagado(self):
        self.login(self.recepcion)
        with patch('pacientes.views.SimpleDocTemplate'), \
                patch('pacientes.views.Paragraph') as mock_paragraph:
            response = self.client.get(
                reverse('pacientes:descargar_pdf', args=[self.paciente.pk])
            )

        self.assertEqual(response.status_code, 200)
        textos = [llamada[0][0] for llamada in mock_paragraph.call_args_list]
        self.assertFalse(any(TEXTO_NOTA in texto for texto in textos))

    def test_pdf_incluye_las_notas_para_recepcion_por_defecto(self):
        self.login(self.recepcion)
        with patch('pacientes.views.SimpleDocTemplate'), \
                patch('pacientes.views.Paragraph') as mock_paragraph:
            response = self.client.get(
                reverse('pacientes:descargar_pdf', args=[self.paciente.pk])
            )

        self.assertEqual(response.status_code, 200)
        textos = [llamada[0][0] for llamada in mock_paragraph.call_args_list]
        self.assertTrue(any(TEXTO_NOTA in texto for texto in textos))

    def test_pdf_incluye_las_notas_para_el_profesional(self):
        self.login(self.user_a)
        with patch('pacientes.views.SimpleDocTemplate'), \
                patch('pacientes.views.Paragraph') as mock_paragraph:
            response = self.client.get(
                reverse('pacientes:descargar_pdf', args=[self.paciente.pk])
            )

        self.assertEqual(response.status_code, 200)
        textos = [llamada[0][0] for llamada in mock_paragraph.call_args_list]
        self.assertTrue(any(TEXTO_NOTA in texto for texto in textos))

    def test_profesional_ajeno_no_puede_ver_paciente_ni_notas(self):
        self.login(self.user_b)

        detalle = self.client.get(
            reverse('pacientes:detalle', args=[self.paciente.pk])
        )
        self.assertEqual(detalle.status_code, 404)

    def test_no_se_crean_notas_vacias_ni_demasiado_largas(self):
        self.login(self.user_a)

        self.client.post(self.url_crear(), {'texto': '   '})
        self.client.post(self.url_crear(), {'texto': 'x' * 10001})

        self.assertEqual(
            NotaClinica.objects.filter(paciente=self.paciente).count(),
            1,
        )

    def test_notas_se_paginan_de_a_20(self):
        for indice in range(21):
            NotaClinica.objects.create(
                paciente=self.paciente,
                autor=self.user_a,
                texto=f'Nota extra {indice}',
            )

        self.login(self.user_a)
        response = self.client.get(
            reverse('pacientes:detalle', args=[self.paciente.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['notas_page'].paginator.count, 22)
        self.assertEqual(len(response.context['notas_page'].object_list), 20)

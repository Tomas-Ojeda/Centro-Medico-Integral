from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Especialidad, Profesional


class ProfesionalEspecialidadTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='recepcion',
            password='clave-segura-123',
        )
        self.client.force_login(self.user)

    def datos_profesional(self, **overrides):
        datos = {
            'nombre': 'Ana',
            'apellido': 'García',
            'dni': '30111222',
            'matricula_nacional': 'MP 1234',
            'matricula_provincial': '',
            'telefono': '',
            'email': 'ana.garcia@example.com',
            'fecha_ingreso': '2020-01-15',
            'activo': 'on',
            'especialidades': '',
        }
        datos.update(overrides)
        return datos

    def test_crear_sin_especialidad_y_editar_con_una_se_guarda_y_se_ve(self):
        response = self.client.post(
            reverse('profesionales:crear'),
            self.datos_profesional(),
        )
        self.assertEqual(response.status_code, 302)

        profesional = Profesional.objects.get(dni='30111222')
        self.assertEqual(profesional.especialidades.count(), 0)

        response = self.client.post(
            reverse('profesionales:editar', args=[profesional.pk]),
            self.datos_profesional(especialidades='Cardiología'),
        )
        self.assertEqual(response.status_code, 302)

        profesional.refresh_from_db()
        self.assertEqual(
            list(profesional.especialidades.values_list('nombre', flat=True)),
            ['Cardiología'],
        )

        response = self.client.get(reverse('profesionales:lista'))
        self.assertContains(response, 'Cardiología')

    def test_editar_con_dos_especialidades_se_ven_en_la_lista(self):
        self.client.post(
            reverse('profesionales:crear'),
            self.datos_profesional(),
        )
        profesional = Profesional.objects.get(dni='30111222')

        response = self.client.post(
            reverse('profesionales:editar', args=[profesional.pk]),
            self.datos_profesional(
                especialidades='Cardiología, Clínica Médica',
            ),
        )
        self.assertEqual(response.status_code, 302)

        profesional.refresh_from_db()
        self.assertEqual(profesional.especialidades.count(), 2)

        response = self.client.get(reverse('profesionales:lista'))
        self.assertContains(response, 'Cardiología')
        self.assertContains(response, 'Clínica Médica')

    def test_especialidades_no_se_duplican_por_mayusculas_ni_espacios(self):
        self.client.post(
            reverse('profesionales:crear'),
            self.datos_profesional(especialidades='cardiología'),
        )
        profesional = Profesional.objects.get(dni='30111222')

        self.client.post(
            reverse('profesionales:editar', args=[profesional.pk]),
            self.datos_profesional(
                especialidades='  Cardiología,  cardiología  ',
            ),
        )

        self.assertEqual(
            Especialidad.objects.filter(nombre__iexact='cardiología').count(),
            1,
        )
        self.assertEqual(profesional.especialidades.count(), 1)

    def test_especialidad_con_espacios_internos_se_normaliza(self):
        self.client.post(
            reverse('profesionales:crear'),
            self.datos_profesional(especialidades='  Clínica   Médica  '),
        )
        profesional = Profesional.objects.get(dni='30111222')

        self.assertEqual(
            list(profesional.especialidades.values_list('nombre', flat=True)),
            ['Clínica Médica'],
        )

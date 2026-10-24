from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from pacientes.models import Paciente
from profesionales.models import Especialidad, Profesional
from .models import Consulta


class ConsultaEspecialidadTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='recepcion',
            password='clave-segura-123',
        )
        self.client.force_login(self.user)
        self.paciente = Paciente.objects.create(
            dni='30111222',
            nombre='Ana',
            apellido='Pérez',
            fecha_nacimiento=date(1985, 4, 12),
        )
        self.fecha_hora = timezone.localtime(timezone.now()).replace(
            hour=10,
            minute=0,
            second=0,
            microsecond=0,
        )
        self.profesional = Profesional.objects.create(
            nombre='Ana',
            apellido='García',
            dni='30111222',
            fecha_ingreso=date(2020, 1, 15),
        )

    def crear_consulta(self):
        return self.client.post(
            reverse('historias:nueva_consulta', args=[self.paciente.pk]),
            {
                'profesional': self.profesional.pk,
                'fecha_hora': self.fecha_hora.strftime('%Y-%m-%dT%H:%M'),
                'motivo': 'Control',
                'diagnostico': 'Control general',
                'evolucion': '',
                'tratamiento': '',
            },
        )

    def test_consulta_creada_sin_especialidad_usa_la_actual_como_fallback(self):
        self.assertEqual(self.crear_consulta().status_code, 302)
        consulta = Consulta.objects.get()
        self.assertEqual(consulta.especialidad, '')

        self.profesional.especialidades.create(nombre='Cardiología')

        response = self.client.get(
            reverse('pacientes:detalle', args=[self.paciente.pk]),
        )
        self.assertContains(response, 'Cardiología')

    def test_consulta_mantiene_la_especialidad_historica(self):
        self.profesional.especialidades.create(nombre='Cardiología')
        self.crear_consulta()

        clinica_medica = Especialidad.objects.create(nombre='Clínica Médica')
        self.profesional.especialidades.set([clinica_medica])

        response = self.client.get(
            reverse('pacientes:detalle', args=[self.paciente.pk]),
        )
        self.assertContains(response, 'Cardiología')
        self.assertNotContains(response, 'Clínica Médica')

    def test_pdf_usa_la_especialidad_actual_como_fallback(self):
        self.crear_consulta()
        self.profesional.especialidades.create(nombre='Cardiología')

        with patch('pacientes.views.SimpleDocTemplate'), \
                patch('pacientes.views.Paragraph') as mock_paragraph:
            response = self.client.get(
                reverse('pacientes:descargar_pdf', args=[self.paciente.pk]),
            )

        self.assertEqual(response.status_code, 200)
        textos = [llamada[0][0] for llamada in mock_paragraph.call_args_list]
        self.assertTrue(
            any('Especialidad' in texto and 'Cardiología' in texto for texto in textos)
        )

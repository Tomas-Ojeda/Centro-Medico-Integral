from datetime import date

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from consultorio_salto.permisos import GRUPO_PROFESIONAL, GRUPO_RECEPCION
from pacientes.models import Paciente
from profesionales.models import Profesional
from turnos.models import Plazo, SolicitudTurno


PAGINAS_AUTENTICADAS = [
    'dashboard:index',
    'pacientes:lista',
    'turnos:agenda',
    'derivaciones:lista',
    'profesionales:lista',
]


class BaseResponsiveTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.grupo_recepcion, _ = Group.objects.get_or_create(
            name=GRUPO_RECEPCION
        )
        cls.grupo_profesional, _ = Group.objects.get_or_create(
            name=GRUPO_PROFESIONAL
        )

        cls.recepcion = User.objects.create_user(
            username='recepcion_movil',
            password='ClaveSegura2026!',
        )
        cls.recepcion.groups.add(cls.grupo_recepcion)

        cls.profesional_user = User.objects.create_user(
            username='profesional_movil',
            password='ClaveSegura2026!',
        )
        cls.profesional_user.groups.add(cls.grupo_profesional)

        cls.profesional = Profesional.objects.create(
            nombre='Ana',
            apellido='Gómez',
            dni='32000001',
            fecha_ingreso=date(2020, 1, 15),
            usuario=cls.profesional_user,
        )

        cls.paciente = Paciente.objects.create(
            dni='33000001',
            nombre='Lucía',
            apellido='Fernández',
            fecha_nacimiento=date(1985, 4, 12),
        )

        SolicitudTurno.objects.create(
            paciente=cls.paciente,
            profesional=cls.profesional,
            solicitado_por=cls.profesional_user,
            plazo=Plazo.UNA_SEMANA,
            fecha_sugerida=date(2026, 12, 1),
        )


class MobileNavigationTests(BaseResponsiveTests):
    def setUp(self):
        self.client.force_login(self.recepcion)

    def test_paginas_autenticadas_incluyen_soporte_movil(self):
        for nombre in PAGINAS_AUTENTICADAS:
            with self.subTest(pagina=nombre):
                response = self.client.get(reverse(nombre))
                self.assertEqual(response.status_code, 200)
                self.assertContains(
                    response,
                    'content="width=device-width, initial-scale=1.0, viewport-fit=cover"',
                )
                self.assertContains(response, 'name="theme-color"')
                self.assertContains(response, 'id="menu-toggle"')
                self.assertContains(response, 'aria-label="Abrir menú"')
                self.assertContains(response, 'aria-controls="sidebar"')
                self.assertContains(response, 'id="sidebar-overlay"')
                self.assertContains(response, 'class="sidebar-overlay"')

    def test_login_incluye_viewport_movil(self):
        self.client.logout()
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'content="width=device-width, initial-scale=1.0, viewport-fit=cover"',
        )
        self.assertContains(response, 'name="theme-color"')

    def test_hamburguesa_muestra_puntito_con_pendientes(self):
        response = self.client.get(reverse('dashboard:index'))
        self.assertContains(response, 'class="menu-toggle-dot"')

    def test_contador_de_pendientes_visible_en_el_cajon(self):
        response = self.client.get(reverse('dashboard:index'))
        self.assertContains(
            response,
            'title="Solicitudes de turno pendientes">1</span>',
        )

    def test_recepcion_conserva_enlaces_de_su_rol(self):
        response = self.client.get(reverse('dashboard:index'))
        self.assertContains(response, reverse('turnos:por_agendar'))
        self.assertContains(response, reverse('profesionales:lista'))

    def test_profesional_no_ve_enlaces_de_recepcion(self):
        self.client.force_login(self.profesional_user)
        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, reverse('profesionales:lista'))
        self.assertContains(response, reverse('derivaciones:lista'))

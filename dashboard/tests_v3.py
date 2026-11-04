"""Pruebas del rediseño V3: sidebar, decoraciones y dashboard."""

import re
from datetime import date

from django.contrib.auth.models import Group, User
from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse

from profesionales.models import Profesional

from consultorio_salto.permisos import GRUPO_PROFESIONAL, GRUPO_RECEPCION

CLAVE = 'ClaveSegura2026!'
EMOJI = re.compile('[\U0001F300-\U0001FAFF\u2600-\u27BF]')


class DashboardV3Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        grupo_recepcion, _ = Group.objects.get_or_create(name=GRUPO_RECEPCION)
        grupo_profesional, _ = Group.objects.get_or_create(name=GRUPO_PROFESIONAL)

        cls.recepcion = User.objects.create_user(
            username='recepcion_v3',
            password=CLAVE,
        )
        cls.recepcion.groups.add(grupo_recepcion)

        cls.admin = User.objects.create_superuser(
            username='admin_v3',
            email='admin_v3@example.com',
            password=CLAVE,
        )

        cls.profesional_user = User.objects.create_user(
            username='profesional_v3',
            password=CLAVE,
        )
        cls.profesional_user.groups.add(grupo_profesional)
        cls.profesional = Profesional.objects.create(
            nombre='Ana',
            apellido='V3',
            dni='39000001',
            email='ana.v3@example.com',
            fecha_ingreso=date(2020, 1, 15),
            usuario=cls.profesional_user,
        )

    def _login(self, user):
        self.client.force_login(user)
        return self.client.get(reverse('dashboard:index'))

    def test_dashboard_renderiza_para_admin_recepcion_y_profesional(self):
        for user in (self.admin, self.recepcion, self.profesional_user):
            with self.subTest(usuario=user.username):
                response = self._login(user)
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, 'dashboard/index.html')
                self.assertContains(response, 'class="main-content"')
                self.assertContains(response, 'class="stats-grid"')

    def test_base_incluye_sidebar_y_decoraciones_v3(self):
        response = self._login(self.recepcion)

        self.assertContains(response, 'class="sidebar"')
        self.assertContains(response, 'class="sidebar-deco sidebar-deco--top"')
        self.assertContains(response, 'class="sidebar-deco sidebar-deco--bottom"')
        self.assertContains(response, 'class="main-deco main-deco--top"')
        self.assertContains(response, 'class="main-deco main-deco--bottom"')
        self.assertContains(response, 'img/logo-blanco-256.png')
        self.assertContains(response, 'fa-table-cells-large')
        self.assertContains(response, 'fa-calendar-days')
        self.assertContains(response, 'fa-share-from-square')
        self.assertContains(response, 'fa-user-doctor')
        self.assertContains(response, 'Cerrar sesión')
        self.assertContains(response, 'class="theme-toggle"')
        self.assertContains(response, 'toggle-label">Paleta')
        self.assertContains(response, 'toggle-label">Tema')

    def test_dashboard_incluye_linea_de_latido(self):
        response = self._login(self.recepcion)

        self.assertContains(response, 'class="header-deco"')
        self.assertContains(response, 'header-beat-grad')

    def test_otras_paginas_no_incluyen_la_linea_de_latido(self):
        self.client.force_login(self.recepcion)
        response = self.client.get(reverse('pacientes:lista'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'header-beat-grad')

    def test_dashboard_no_contiene_emojis(self):
        response = self._login(self.recepcion)
        contenido = response.content.decode('utf-8')

        self.assertIsNone(EMOJI.search(contenido))

    def test_accesos_rapidos_de_recepcion_y_admin(self):
        for user in (self.admin, self.recepcion):
            with self.subTest(usuario=user.username):
                response = self._login(user)
                self.assertContains(response, 'quick-action--primary')
                self.assertContains(response, '> Nuevo Paciente')
                self.assertContains(response, 'quick-action--secondary')
                self.assertContains(response, '> Nuevo Turno')
                self.assertContains(response, '> + Profesional')
                self.assertContains(response, '> Ver Agenda')

    def test_accesos_rapidos_del_profesional(self):
        response = self._login(self.profesional_user)

        self.assertNotContains(response, 'Nuevo Paciente')
        self.assertNotContains(response, 'Nuevo Turno')
        self.assertNotContains(response, '+ Profesional')
        self.assertContains(response, '> Ver Agenda')
        self.assertContains(response, '> Ver Pacientes')

    def test_caja_del_dia_solo_para_recepcion_y_admin(self):
        for user in (self.admin, self.recepcion):
            with self.subTest(usuario=user.username):
                response = self._login(user)
                self.assertContains(response, 'Caja del día')
                self.assertContains(response, 'fa-cash-register')
                self.assertContains(response, 'fa-money-bill-wave')
                self.assertContains(response, 'fa-building-columns')
                self.assertContains(response, 'fa-circle-check')
                self.assertContains(response, 'fa-receipt')
                self.assertContains(
                    response,
                    'Registro interno de cobro. No es comprobante fiscal.',
                )

        response = self._login(self.profesional_user)
        self.assertNotContains(response, 'fa-cash-register')
        self.assertNotContains(
            response,
            'Registro interno de cobro. No es comprobante fiscal.',
        )

    def test_semana_muestra_siete_tarjetas_de_dia(self):
        response = self._login(self.recepcion)
        contenido = response.content.decode('utf-8')

        self.assertEqual(len(re.findall(r'class="week-day[\s"]', contenido)), 7)
        self.assertContains(response, 'class="week-day is-today"')
        self.assertContains(response, 'aria-current="date"')

    def test_estado_vacio_de_turnos_de_hoy(self):
        response = self._login(self.recepcion)

        self.assertContains(response, 'No hay turnos para hoy')
        self.assertContains(response, 'agenda-empty')
        self.assertContains(response, 'Ver agenda')

    def test_assets_nuevos_del_login_existen(self):
        for asset in (
            'img/logo-color-transparente.png',
            'img/fondo-consultorio.jpg',
        ):
            with self.subTest(asset=asset):
                self.assertIsNotNone(finders.find(asset))

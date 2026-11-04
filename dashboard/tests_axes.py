"""Pruebas del bloqueo de login (django-axes) y del usuario sin mayúsculas."""

from io import StringIO

from axes.utils import reset as axes_reset
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse

from consultorio_salto.permisos import GRUPO_RECEPCION

CLAVE = 'ClaveSegura2026!'
IP_CONSULTORIO = '203.0.113.77'


class AxesLockoutTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        grupo_recepcion, _ = Group.objects.get_or_create(name=GRUPO_RECEPCION)

        cls.usuario_a = User.objects.create_user(
            username='usuario_axes_a',
            password=CLAVE,
        )
        cls.usuario_a.groups.add(grupo_recepcion)

        cls.usuario_b = User.objects.create_user(
            username='usuario_axes_b',
            password=CLAVE,
        )
        cls.usuario_b.groups.add(grupo_recepcion)

    def setUp(self):
        axes_reset()

    def tearDown(self):
        axes_reset()

    def fallar(self, username, veces=8, ip=IP_CONSULTORIO):
        response = None
        for _ in range(veces):
            response = self.client.post(
                reverse('login'),
                {'username': username, 'password': 'incorrecta'},
                REMOTE_ADDR=ip,
            )
        return response

    def test_ocho_fallos_no_bloquean_a_otro_usuario_de_la_misma_ip(self):
        response = self.fallar(self.usuario_a.username)
        self.assertEqual(response.status_code, 429)

        response = self.client.post(
            reverse('login'),
            {'username': self.usuario_a.username, 'password': CLAVE},
            REMOTE_ADDR=IP_CONSULTORIO,
        )
        self.assertEqual(response.status_code, 429)

        response = self.client.post(
            reverse('login'),
            {'username': self.usuario_b.username, 'password': CLAVE},
            REMOTE_ADDR=IP_CONSULTORIO,
        )
        self.assertRedirects(response, reverse('dashboard:index'))

    def test_bloqueo_muestra_pagina_en_espanol_con_codigo_429(self):
        response = self.fallar(self.usuario_a.username)

        self.assertEqual(response.status_code, 429)
        self.assertContains(response, 'Acceso bloqueado', status_code=429)
        self.assertContains(
            response,
            'Demasiados intentos fallidos. Por seguridad, el acceso con este '
            'usuario está bloqueado temporalmente.',
            status_code=429,
        )
        self.assertContains(response, '15 minutos', status_code=429)
        self.assertContains(
            response,
            'Volver al inicio de sesión',
            status_code=429,
        )
        self.assertContains(response, 'role="alert"', status_code=429)
        self.assertNotContains(
            response,
            self.usuario_a.username,
            status_code=429,
        )

    def test_login_no_distingue_mayusculas(self):
        user = User.objects.create_user(
            username='Peralta',
            password=CLAVE,
        )
        user.groups.add(Group.objects.get(name=GRUPO_RECEPCION))

        response = self.client.post(
            reverse('login'),
            {'username': 'peralta', 'password': CLAVE},
        )
        self.assertRedirects(response, reverse('dashboard:index'))

        self.client.logout()
        response = self.client.post(
            reverse('login'),
            {'username': 'Peralta', 'password': CLAVE},
        )
        self.assertRedirects(response, reverse('dashboard:index'))

    def test_login_con_usuarios_ambiguos_usa_coincidencia_exacta(self):
        # Si existen dos usuarios que solo difieren en mayúsculas, se usa el
        # nombre exacto para no elegir una cuenta al azar.
        User.objects.create_user(username='Duplicado', password=CLAVE)
        User.objects.create_user(username='duplicado', password=CLAVE)
        grupo = Group.objects.get(name=GRUPO_RECEPCION)
        User.objects.get(username='Duplicado').groups.add(grupo)
        User.objects.get(username='duplicado').groups.add(grupo)

        for username in ('Duplicado', 'duplicado'):
            with self.subTest(username=username):
                self.client.logout()
                response = self.client.post(
                    reverse('login'),
                    {'username': username, 'password': CLAVE},
                )
                self.assertRedirects(response, reverse('dashboard:index'))

    def test_login_exitoso_reinicia_los_fallos(self):
        self.fallar(self.usuario_a.username, veces=3)

        response = self.client.post(
            reverse('login'),
            {'username': self.usuario_a.username, 'password': CLAVE},
        )
        self.assertRedirects(response, reverse('dashboard:index'))
        self.client.logout()

        # Si el contador no se hubiera reiniciado, el séptimo fallo nuevo
        # habría llegado a 10 y bloquearía.
        response = self.fallar(self.usuario_a.username, veces=7)
        self.assertEqual(response.status_code, 200)

        response = self.fallar(self.usuario_a.username, veces=1)
        self.assertEqual(response.status_code, 429)

    def test_verificar_usernames_avisa_conflictos_sin_modificar(self):
        User.objects.create_user(username='Peralta', password=CLAVE)
        User.objects.create_user(username='peralta', password=CLAVE)

        salida = StringIO()
        errores = StringIO()
        with self.assertRaises(CommandError):
            call_command(
                'verificar_usernames',
                stdout=salida,
                stderr=errores,
            )

        mensaje = errores.getvalue()
        self.assertIn('Peralta', mensaje)
        self.assertIn('peralta', mensaje)
        self.assertIn('No se modificó ningún usuario', mensaje)
        self.assertTrue(User.objects.filter(username='Peralta').exists())
        self.assertTrue(User.objects.filter(username='peralta').exists())

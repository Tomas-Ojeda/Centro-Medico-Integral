import json
from pathlib import Path

from axes.utils import reset as axes_reset
from django.contrib.auth.models import Group, User
from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse

from consultorio_salto.permisos import GRUPO_RECEPCION

ASSETS = (
    'img/logo-color.png',
    'img/logo-blanco-256.png',
    'img/logo-blanco-512.png',
    'img/favicon-32.png',
    'img/apple-touch-icon-180.png',
    'img/icon-192.png',
    'img/icon-512.png',
    'manifest.webmanifest',
)


class LoginVisualTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        grupo_recepcion, _ = Group.objects.get_or_create(name=GRUPO_RECEPCION)
        cls.user = User.objects.create_user(
            username='recepcion_login',
            password='ClaveSegura2026!',
        )
        cls.user.groups.add(grupo_recepcion)

    def setUp(self):
        axes_reset()

    def tearDown(self):
        axes_reset()

    def test_login_responde_200_con_campos_y_viewport(self):
        response = self.client.get(reverse('login'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="viewport"')
        self.assertContains(
            response,
            'content="width=device-width, initial-scale=1.0, viewport-fit=cover"',
        )
        self.assertContains(response, 'name="theme-color"')
        self.assertContains(response, 'content="#14245c"')
        self.assertContains(response, 'id="id_username"')
        self.assertContains(response, 'id="id_password"')
        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'name="password"')
        self.assertContains(response, 'autocomplete="username"')
        self.assertContains(response, 'autocomplete="current-password"')
        self.assertContains(response, 'autocapitalize="none"')
        self.assertContains(response, 'spellcheck="false"')
        self.assertContains(response, 'autofocus')
        self.assertContains(response, 'Ingresar al sistema')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')

    def test_login_muestra_el_saludo_nuevo(self):
        response = self.client.get(reverse('login'))

        self.assertContains(response, 'Qué bueno verte')
        self.assertContains(response, 'Ingresá tus credenciales para acceder al sistema')

    def test_login_no_usa_placeholders_ni_textos_viejos(self):
        response = self.client.get(reverse('login'))

        self.assertNotContains(response, 'via.placeholder.com')
        self.assertNotContains(response, 'bg-logo')
        self.assertNotContains(response, 'Bienvenido')
        self.assertNotContains(response, 'Bienvenida')
        self.assertNotContains(response, 'fonts.googleapis.com')
        self.assertNotContains(response, 'Recordarme')
        self.assertNotContains(response, 'Olvidé mi contraseña')

    def test_login_incluye_contactos_y_datos_del_centro(self):
        response = self.client.get(reverse('login'))

        self.assertContains(response, 'https://www.instagram.com/consultoriosmedicos.salto/')
        self.assertContains(response, 'tel:2604018478')
        self.assertContains(response, 'https://www.facebook.com/consultorios.medicos.2023')
        self.assertContains(response, 'maps.google.com')
        self.assertContains(response, '>Consultorios Médicos</h1>')
        self.assertContains(response, '>Salto de las Rosas</p>')
        self.assertContains(response, 'Ruta Nacional 143')

    def test_login_aplica_el_tema_guardado_sin_parpadeo(self):
        response = self.client.get(reverse('login'))

        self.assertContains(response, "localStorage.getItem('theme')")
        self.assertContains(response, 'prefers-color-scheme: dark')
        self.assertContains(response, 'data-theme')

    def test_login_tiene_boton_accesible_para_mostrar_la_clave(self):
        response = self.client.get(reverse('login'))

        self.assertContains(response, 'id="toggle-password"')
        self.assertContains(response, 'aria-label="Mostrar contraseña"')
        self.assertContains(response, 'aria-pressed="false"')
        self.assertContains(response, 'aria-controls="id_password"')

    def test_los_assets_existen_en_los_finders(self):
        for asset in ASSETS:
            with self.subTest(asset=asset):
                self.assertIsNotNone(finders.find(asset), f'Falta el asset: {asset}')

    def test_el_manifest_es_valido(self):
        path = finders.find('manifest.webmanifest')
        data = json.loads(Path(path).read_text(encoding='utf-8'))

        self.assertEqual(data['name'], 'Consultorios Médicos')
        self.assertEqual(data['short_name'], 'Consultorios')
        self.assertEqual(data['display'], 'standalone')
        self.assertEqual(data['start_url'], '/')
        self.assertEqual(data['theme_color'], '#14245c')
        self.assertEqual(
            [icon['sizes'] for icon in data['icons']],
            ['192x192', '512x512'],
        )

    def test_login_valido_redirige_al_dashboard(self):
        response = self.client.post(
            reverse('login'),
            {'username': self.user.username, 'password': 'ClaveSegura2026!'},
        )

        self.assertRedirects(response, reverse('dashboard:index'))

    def test_login_conserva_el_parametro_next(self):
        response = self.client.post(
            reverse('login') + '?next=/pacientes/',
            {'username': self.user.username, 'password': 'ClaveSegura2026!'},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/pacientes/')

    def test_login_invalido_muestra_error_con_role_alert(self):
        response = self.client.post(
            reverse('login'),
            {'username': self.user.username, 'password': 'incorrecta'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'role="alert"')
        self.assertContains(response, 'Por favor introduzca un nombre de usuario y una contraseña correctos')

    def test_axes_bloquea_y_usa_la_plantilla_del_login(self):
        for _ in range(6):
            response = self.client.post(
                reverse('login'),
                {'username': self.user.username, 'password': 'incorrecta'},
            )

        self.assertEqual(response.status_code, 429)
        self.assertContains(response, 'Acceso bloqueado', status_code=429)
        self.assertContains(response, 'Volver al inicio de sesión', status_code=429)
        self.assertContains(response, 'role="alert"', status_code=429)

        response = self.client.post(
            reverse('login'),
            {'username': self.user.username, 'password': 'ClaveSegura2026!'},
        )
        self.assertEqual(response.status_code, 429)

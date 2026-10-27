import re
from math import pow
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from consultorio_salto.permisos import GRUPO_PROFESIONAL, GRUPO_RECEPCION

from .models import PALETAS, PreferenciaUsuario


CLAVE = 'ClaveSegura2026!'
PALETAS_ESPERADAS = {clave for clave, _ in PALETAS}


def _leer_archivo(*partes):
    return Path(settings.BASE_DIR, *partes).read_text(encoding='utf-8')


def _parsear_declaraciones(body):
    return {
        nombre: valor.lower()
        for nombre, valor in re.findall(
            r'(--[\w-]+)\s*:\s*(#[0-9a-fA-F]{6})',
            body,
        )
    }


def _parsear_bloques(css, patron):
    return {
        nombre: _parsear_declaraciones(body)
        for nombre, body in re.findall(patron, css, re.S)
    }


def _luminancia(color):
    color = color.lstrip('#')
    canales = [int(color[i:i + 2], 16) / 255 for i in (0, 2, 4)]

    def ajustar(canal):
        if canal <= 0.04045:
            return canal / 12.92
        return pow((canal + 0.055) / 1.055, 2.4)

    rojo, verde, azul = (ajustar(canal) for canal in canales)
    return 0.2126 * rojo + 0.7152 * verde + 0.0722 * azul


def _contraste(color_a, color_b):
    luminancia_a = _luminancia(color_a)
    luminancia_b = _luminancia(color_b)
    claro = max(luminancia_a, luminancia_b)
    oscuro = min(luminancia_a, luminancia_b)
    return (claro + 0.05) / (oscuro + 0.05)


class BasePreferenciasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        grupo_recepcion, _ = Group.objects.get_or_create(name=GRUPO_RECEPCION)
        grupo_profesional, _ = Group.objects.get_or_create(
            name=GRUPO_PROFESIONAL
        )

        cls.recepcion = User.objects.create_user(
            username='recepcion_paletas',
            password=CLAVE,
        )
        cls.recepcion.groups.add(grupo_recepcion)

        cls.profesional = User.objects.create_user(
            username='profesional_paletas',
            password=CLAVE,
        )
        cls.profesional.groups.add(grupo_profesional)

        cls.admin = User.objects.create_superuser(
            username='admin_paletas',
            email='admin_paletas@example.com',
            password=CLAVE,
        )

        cls.user_a = User.objects.create_user(
            username='usuario_paleta_a',
            password=CLAVE,
        )
        cls.user_a.groups.add(grupo_recepcion)

        cls.user_b = User.objects.create_user(
            username='usuario_paleta_b',
            password=CLAVE,
        )
        cls.user_b.groups.add(grupo_recepcion)

    def login(self, user):
        self.client.force_login(user)


class PaletaUsuarioTests(BasePreferenciasTests):
    def test_usuario_nuevo_usa_predeterminado_sin_crear_registro(self):
        self.login(self.recepcion)

        response = self.client.get(reverse('dashboard:index'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-palette="predeterminado"')
        self.assertFalse(
            PreferenciaUsuario.objects.filter(usuario=self.recepcion).exists()
        )

    def test_html_refleja_la_paleta_de_cada_usuario(self):
        for indice, (clave, _) in enumerate(PALETAS):
            with self.subTest(paleta=clave):
                user = User.objects.create_user(
                    username=f'paleta_{clave}_{indice}',
                    password=CLAVE,
                )
                user.groups.add(Group.objects.get(name=GRUPO_RECEPCION))
                PreferenciaUsuario.objects.create(
                    usuario=user,
                    paleta=clave,
                )
                self.login(user)

                response = self.client.get(reverse('dashboard:index'))

                self.assertContains(
                    response,
                    f'data-palette="{clave}"',
                )

    def test_post_valido_guarda_solo_la_paleta_del_usuario_actual(self):
        self.login(self.user_a)

        response = self.client.post(
            reverse('preferencias:paleta'),
            {'paleta': 'menta'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'ok': True, 'paleta': 'menta'})
        self.assertEqual(
            PreferenciaUsuario.objects.get(usuario=self.user_a).paleta,
            'menta',
        )
        self.assertFalse(
            PreferenciaUsuario.objects.filter(usuario=self.user_b).exists()
        )

        self.login(self.user_b)
        response = self.client.post(
            reverse('preferencias:paleta'),
            {'paleta': 'rosa'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            PreferenciaUsuario.objects.get(usuario=self.user_a).paleta,
            'menta',
        )
        self.assertEqual(
            PreferenciaUsuario.objects.get(usuario=self.user_b).paleta,
            'rosa',
        )

    def test_todos_los_roles_pueden_guardar_su_paleta(self):
        for user in (self.admin, self.recepcion, self.profesional):
            with self.subTest(usuario=user.username):
                self.login(user)
                response = self.client.post(
                    reverse('preferencias:paleta'),
                    {'paleta': 'cielo'},
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    PreferenciaUsuario.objects.get(usuario=user).paleta,
                    'cielo',
                )

    def test_paleta_invalida_devuelve_400_y_no_guarda(self):
        self.login(self.recepcion)

        response = self.client.post(
            reverse('preferencias:paleta'),
            {'paleta': 'neon'},
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['ok'])
        self.assertFalse(
            PreferenciaUsuario.objects.filter(usuario=self.recepcion).exists()
        )

    def test_anonimo_redirige_al_login(self):
        response = self.client.post(
            reverse('preferencias:paleta'),
            {'paleta': 'menta'},
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_usuario_sin_rol_recibe_403(self):
        sin_rol = User.objects.create_user(
            username='sin_rol_paletas',
            password=CLAVE,
        )
        self.login(sin_rol)

        response = self.client.post(
            reverse('preferencias:paleta'),
            {'paleta': 'menta'},
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            PreferenciaUsuario.objects.filter(usuario=sin_rol).exists()
        )

    def test_get_devuelve_405(self):
        self.login(self.recepcion)

        response = self.client.get(reverse('preferencias:paleta'))

        self.assertEqual(response.status_code, 405)

    def test_login_muestra_titulo_y_localidad_separados(self):
        response = self.client.get(reverse('login'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '>Consultorios Médicos</h1>')
        self.assertContains(response, '>Salto de las Rosas</p>')


class PaletasContrasteTests(SimpleTestCase):
    def test_paletas_cumplen_contraste_wcag(self):
        css_paletas = _leer_archivo(
            'templates',
            'includes',
            '_paletas.html',
        )
        base = _leer_archivo('templates', 'base.html')

        raiz = re.search(r':root\s*\{(.*?)\}', base, re.S)
        oscuro_base = re.search(
            r'\[data-theme="dark"\]\s*\{(.*?)\}',
            base,
            re.S,
        )
        self.assertIsNotNone(raiz)
        self.assertIsNotNone(oscuro_base)

        claras = _parsear_bloques(
            css_paletas,
            r'(?<!\])\[data-palette="([^"]+)"\]\s*\{(.*?)\}',
        )
        oscuras = _parsear_bloques(
            css_paletas,
            r'\[data-theme="dark"\]\[data-palette="([^"]+)"\]\s*\{(.*?)\}',
        )

        claras['predeterminado'] = _parsear_declaraciones(raiz.group(1))
        oscuras['predeterminado'] = _parsear_declaraciones(
            oscuro_base.group(1)
        )

        self.assertEqual(set(claras), PALETAS_ESPERADAS)
        self.assertEqual(set(oscuras), PALETAS_ESPERADAS)

        texto_primario_claro = claras['predeterminado']['--text-primary']
        texto_secundario_claro = claras['predeterminado']['--text-secondary']
        texto_primario_oscuro = oscuras['predeterminado']['--text-primary']
        texto_secundario_oscuro = oscuras['predeterminado']['--text-secondary']

        for clave in PALETAS_ESPERADAS:
            with self.subTest(paleta=clave, modo='claro'):
                paleta = claras[clave]
                fondo_principal = paleta['--bg-main']
                fondo_tarjeta = paleta.get('--bg-card', '#ffffff')
                acento = paleta['--accent']

                self.assertGreaterEqual(
                    _contraste(texto_primario_claro, fondo_principal),
                    4.5,
                )
                self.assertGreaterEqual(
                    _contraste(texto_secundario_claro, fondo_principal),
                    4.5,
                )
                self.assertGreaterEqual(
                    _contraste(texto_primario_claro, fondo_tarjeta),
                    4.5,
                )
                self.assertGreaterEqual(
                    _contraste(texto_secundario_claro, fondo_tarjeta),
                    4.5,
                )
                self.assertGreaterEqual(
                    _contraste('#1a2035', acento),
                    4.5,
                )
                if '--accent-text' in paleta:
                    self.assertGreaterEqual(
                        _contraste(paleta['--accent-text'], fondo_principal),
                        4.5,
                    )
                    self.assertGreaterEqual(
                        _contraste(paleta['--accent-text'], fondo_tarjeta),
                        4.5,
                    )

            with self.subTest(paleta=clave, modo='oscuro'):
                paleta = oscuras[clave]
                acento = claras[clave]['--accent']

                self.assertEqual(
                    paleta['--input-bg'],
                    paleta['--bg-main'],
                )
                self.assertEqual(
                    paleta['--hover-row'],
                    paleta['--bg-card'],
                )
                self.assertGreaterEqual(
                    _contraste(texto_primario_oscuro, paleta['--bg-main']),
                    4.5,
                )
                self.assertGreaterEqual(
                    _contraste(texto_secundario_oscuro, paleta['--bg-main']),
                    4.5,
                )
                self.assertGreaterEqual(
                    _contraste(texto_primario_oscuro, paleta['--bg-card']),
                    4.5,
                )
                self.assertGreaterEqual(
                    _contraste(texto_secundario_oscuro, paleta['--bg-card']),
                    4.5,
                )
                self.assertGreaterEqual(
                    _contraste('#1a2035', acento),
                    4.5,
                )

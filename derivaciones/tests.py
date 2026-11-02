import tempfile

from django.contrib.auth.models import AnonymousUser, Group, User
from django.core.files.base import ContentFile
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from auditoria.models import LogAcceso
from consultorio_salto.context_processors import roles
from consultorio_salto.permisos import GRUPO_PROFESIONAL, GRUPO_RECEPCION
from historias.models import AdjuntoHistoria, Consulta, NotaClinica
from pacientes.models import Paciente
from profesionales.models import Profesional
from turnos.models import EstadoSolicitud, SolicitudTurno

from .models import Derivacion, EstadoDerivacion


CLAVE = 'ClaveSegura2026!'


class BaseDerivacionesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        grupo_recepcion, _ = Group.objects.get_or_create(name=GRUPO_RECEPCION)
        grupo_profesional, _ = Group.objects.get_or_create(
            name=GRUPO_PROFESIONAL
        )

        cls.recepcion = User.objects.create_user(
            username='recepcion_derivaciones',
            password=CLAVE,
        )
        cls.recepcion.groups.add(grupo_recepcion)

        cls.admin = User.objects.create_superuser(
            username='admin_derivaciones',
            email='admin_derivaciones@example.com',
            password=CLAVE,
        )

        cls.user_a = User.objects.create_user(
            username='prof_deriv_a',
            password=CLAVE,
        )
        cls.user_a.groups.add(grupo_profesional)
        cls.user_b = User.objects.create_user(
            username='prof_deriv_b',
            password=CLAVE,
        )
        cls.user_b.groups.add(grupo_profesional)
        cls.user_c = User.objects.create_user(
            username='prof_deriv_c',
            password=CLAVE,
        )
        cls.user_c.groups.add(grupo_profesional)

        cls.prof_a = Profesional.objects.create(
            nombre='Ana',
            apellido='Derivaciones',
            dni='36000001',
            fecha_ingreso=timezone.localdate(),
            usuario=cls.user_a,
        )
        cls.prof_b = Profesional.objects.create(
            nombre='Beto',
            apellido='Derivaciones',
            dni='36000002',
            fecha_ingreso=timezone.localdate(),
            usuario=cls.user_b,
        )
        cls.prof_c = Profesional.objects.create(
            nombre='Carla',
            apellido='Derivaciones',
            dni='36000003',
            fecha_ingreso=timezone.localdate(),
            usuario=cls.user_c,
        )
        cls.prof_sin_usuario = Profesional.objects.create(
            nombre='Diego',
            apellido='Derivaciones',
            dni='36000004',
            fecha_ingreso=timezone.localdate(),
            usuario=None,
        )

        cls.paciente = Paciente.objects.create(
            dni='36000010',
            nombre='Paciente',
            apellido='Derivado',
            fecha_nacimiento=timezone.localdate().replace(year=1990),
        )
        cls.paciente_c = Paciente.objects.create(
            dni='36000011',
            nombre='Paciente',
            apellido='DeCarla',
            fecha_nacimiento=timezone.localdate().replace(year=1991),
        )

        # A atiende al paciente principal. C atiende a su propio paciente.
        cls.consulta_a = Consulta.objects.create(
            paciente=cls.paciente,
            profesional=cls.prof_a,
            fecha_hora=timezone.now(),
            diagnostico='Control inicial',
        )
        Consulta.objects.create(
            paciente=cls.paciente_c,
            profesional=cls.prof_c,
            fecha_hora=timezone.now(),
            diagnostico='Control de C',
        )

    def login(self, user):
        self.client.force_login(user)

    def crear_derivacion(
        self,
        paciente=None,
        origen=None,
        destino=None,
        estado=EstadoDerivacion.PENDIENTE,
        motivo='Derivación de prueba.',
        crear_solicitud=True,
    ):
        derivacion = Derivacion.objects.create(
            paciente=paciente or self.paciente,
            profesional_origen=origen or self.prof_a,
            profesional_destino=destino or self.prof_b,
            motivo=motivo,
            estado=estado,
            creado_por=self.user_a,
        )
        if crear_solicitud and estado == EstadoDerivacion.PENDIENTE:
            derivacion.crear_solicitud_turno()
        return derivacion

    def url_crear(self, paciente=None):
        return reverse(
            'derivaciones:crear',
            args=[(paciente or self.paciente).pk],
        )


class CreacionDerivacionTests(BaseDerivacionesTests):
    def test_profesional_crea_derivacion_y_solicitud_de_turno(self):
        self.login(self.user_a)
        response = self.client.post(
            self.url_crear(),
            {
                'profesional_destino': self.prof_b.pk,
                'motivo': 'Dolor lumbar persistente.',
            },
        )

        derivacion = Derivacion.objects.get()
        self.assertRedirects(
            response,
            reverse('derivaciones:detalle', args=[derivacion.pk]),
        )
        self.assertEqual(derivacion.paciente, self.paciente)
        self.assertEqual(derivacion.profesional_origen, self.prof_a)
        self.assertEqual(derivacion.profesional_destino, self.prof_b)
        self.assertEqual(derivacion.motivo, 'Dolor lumbar persistente.')
        self.assertEqual(derivacion.estado, EstadoDerivacion.PENDIENTE)
        self.assertEqual(derivacion.creado_por, self.user_a)

        solicitud = derivacion.solicitud_turno
        self.assertIsNotNone(solicitud)
        self.assertEqual(solicitud.paciente, self.paciente)
        self.assertEqual(solicitud.profesional, self.prof_b)
        self.assertEqual(solicitud.estado, EstadoSolicitud.PENDIENTE)
        self.assertIn('Derivado por', solicitud.nota)
        self.assertIn('Dolor lumbar persistente.', solicitud.nota)

        self.assertTrue(
            LogAcceso.objects.filter(
                usuario=self.user_a,
                accion='crear',
                modelo='Derivacion',
                objeto_id=derivacion.pk,
            ).exists()
        )

    def test_motivo_es_obligatorio(self):
        self.login(self.user_a)
        response = self.client.post(
            self.url_crear(),
            {
                'profesional_destino': self.prof_b.pk,
                'motivo': '   ',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Derivacion.objects.exists())

    def test_destino_no_puede_ser_igual_al_origen(self):
        self.login(self.user_a)
        response = self.client.post(
            self.url_crear(),
            {
                'profesional_destino': self.prof_a.pk,
                'motivo': 'Intento inválido.',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Derivacion.objects.exists())

    def test_destino_inactivo_no_es_aceptado(self):
        self.prof_b.activo = False
        self.prof_b.save(update_fields=['activo'])

        self.login(self.user_a)
        response = self.client.post(
            self.url_crear(),
            {
                'profesional_destino': self.prof_b.pk,
                'motivo': 'Intento inválido.',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Derivacion.objects.exists())

    def test_destino_sin_usuario_crea_derivacion_y_avisa(self):
        self.login(self.user_a)
        response = self.client.post(
            self.url_crear(),
            {
                'profesional_destino': self.prof_sin_usuario.pk,
                'motivo': 'Interconsulta.',
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        derivacion = Derivacion.objects.get()
        self.assertIsNotNone(derivacion.solicitud_turno)
        self.assertContains(response, 'no recibirá la notificación en la app')

        formulario = self.client.get(self.url_crear())
        self.assertContains(
            formulario,
            'Los profesionales sin usuario vinculado no reciben '
            'notificaciones en la app.',
        )

    def test_recepcion_no_puede_crear_y_admin_si(self):
        self.login(self.recepcion)
        self.assertEqual(
            self.client.get(self.url_crear()).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                self.url_crear(),
                {
                    'profesional_destino': self.prof_b.pk,
                    'motivo': 'No permitido.',
                },
            ).status_code,
            403,
        )
        self.assertFalse(Derivacion.objects.exists())

        self.login(self.admin)
        formulario = self.client.get(self.url_crear())
        self.assertEqual(formulario.status_code, 200)
        self.assertContains(formulario, 'Profesional de origen')

        response = self.client.post(
            self.url_crear(),
            {
                'profesional_origen': self.prof_a.pk,
                'profesional_destino': self.prof_b.pk,
                'motivo': 'Derivación creada por administración.',
            },
        )
        derivacion = Derivacion.objects.get()
        self.assertRedirects(
            response,
            reverse('derivaciones:detalle', args=[derivacion.pk]),
        )
        self.assertEqual(derivacion.profesional_origen, self.prof_a)
        self.assertEqual(derivacion.creado_por, self.admin)
        self.assertIsNotNone(derivacion.solicitud_turno)

    def test_profesional_no_puede_derivar_paciente_ajeno(self):
        self.login(self.user_b)
        self.assertEqual(
            self.client.get(self.url_crear()).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                self.url_crear(),
                {
                    'profesional_destino': self.prof_c.pk,
                    'motivo': 'No permitido.',
                },
            ).status_code,
            404,
        )
        self.assertFalse(Derivacion.objects.exists())

    def test_reutiliza_la_solicitud_pendiente_existente(self):
        existente = SolicitudTurno.objects.create(
            paciente=self.paciente,
            profesional=self.prof_b,
            fecha_sugerida=timezone.localdate() + timezone.timedelta(days=3),
            solicitado_por=self.user_b,
            nota='Solicitud previa de B.',
        )

        self.login(self.user_a)
        self.client.post(
            self.url_crear(),
            {
                'profesional_destino': self.prof_b.pk,
                'motivo': 'Nuevo motivo de derivación.',
            },
        )

        self.assertEqual(
            SolicitudTurno.objects.filter(
                paciente=self.paciente,
                profesional=self.prof_b,
                estado=EstadoSolicitud.PENDIENTE,
            ).count(),
            1,
        )
        existente.refresh_from_db()
        self.assertEqual(Derivacion.objects.get().solicitud_turno, existente)
        self.assertIn('Nuevo motivo de derivación.', existente.nota)


class AccesoDelDestinoTests(BaseDerivacionesTests):
    def test_acceso_del_destino_tras_la_derivacion(self):
        self.login(self.user_b)

        # Antes de la derivación no tiene ningún vínculo.
        self.assertEqual(
            self.client.get(
                reverse('pacientes:detalle', args=[self.paciente.pk])
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                reverse('pacientes:descargar_pdf', args=[self.paciente.pk])
            ).status_code,
            404,
        )

        derivacion = self.crear_derivacion(
            motivo='Evaluación por dolor lumbar.'
        )

        detalle = self.client.get(
            reverse('pacientes:detalle', args=[self.paciente.pk])
        )
        self.assertEqual(detalle.status_code, 200)
        self.assertContains(detalle, derivacion.motivo)
        self.assertContains(detalle, 'Derivado por')

        pdf = self.client.get(
            reverse('pacientes:descargar_pdf', args=[self.paciente.pk])
        )
        self.assertEqual(pdf.status_code, 200)

        # Puede cargar una consulta.
        response = self.client.post(
            reverse('historias:nueva_consulta', args=[self.paciente.pk]),
            {
                'profesional': self.prof_b.pk,
                'fecha_hora': timezone.localtime(timezone.now()).strftime(
                    '%Y-%m-%dT%H:%M'
                ),
                'motivo': 'Interconsulta',
                'diagnostico': 'Evaluación del destino',
                'evolucion': '',
                'tratamiento': '',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Consulta.objects.filter(
                paciente=self.paciente,
                profesional=self.prof_b,
                diagnostico='Evaluación del destino',
            ).exists()
        )

        # Puede cargar anotaciones.
        response = self.client.post(
            reverse('historias:nueva_nota', args=[self.paciente.pk]),
            {'texto': 'Anotación del profesional destino.'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            NotaClinica.objects.filter(
                paciente=self.paciente,
                autor=self.user_b,
                texto='Anotación del profesional destino.',
            ).exists()
        )

    def test_acceso_a_adjuntos_del_paciente(self):
        derivacion = self.crear_derivacion()

        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                adjunto = AdjuntoHistoria.objects.create(
                    paciente=self.paciente,
                    archivo=ContentFile(
                        b'%PDF-1.4\n',
                        name='estudio.pdf',
                    ),
                    descripcion='Estudio',
                )

                self.login(self.user_b)
                response = self.client.get(
                    reverse(
                        'historias:descargar_adjunto_historia',
                        args=[adjunto.pk],
                    )
                )
                self.assertEqual(response.status_code, 200)
                response.close()

                self.login(self.user_c)
                response = self.client.get(
                    reverse(
                        'historias:descargar_adjunto_historia',
                        args=[adjunto.pk],
                    )
                )
                self.assertEqual(response.status_code, 404)

        self.assertTrue(derivacion.esta_pendiente)

    def test_tercero_sigue_sin_acceso(self):
        self.crear_derivacion()

        self.login(self.user_c)
        self.assertEqual(
            self.client.get(
                reverse('pacientes:detalle', args=[self.paciente.pk])
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                reverse('pacientes:descargar_pdf', args=[self.paciente.pk])
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                reverse('historias:nueva_consulta', args=[self.paciente.pk])
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                reverse('historias:nueva_nota', args=[self.paciente.pk]),
                {'texto': 'No debería poder.'},
            ).status_code,
            404,
        )
        self.assertFalse(
            NotaClinica.objects.filter(
                texto='No debería poder.'
            ).exists()
        )

        # Tampoco ve la derivación ni aparece el paciente en su lista.
        lista = self.client.get(reverse('pacientes:lista'))
        self.assertNotContains(lista, self.paciente.apellido)
        self.assertEqual(
            self.client.get(reverse('derivaciones:lista')).status_code,
            200,
        )
        self.assertNotContains(
            self.client.get(reverse('derivaciones:lista')),
            self.paciente.apellido,
        )

    def test_abrir_derivacion_la_marca_vista_y_audita(self):
        derivacion = self.crear_derivacion()
        self.login(self.user_b)

        response = self.client.get(
            reverse('derivaciones:detalle', args=[derivacion.pk])
        )
        self.assertEqual(response.status_code, 200)

        derivacion.refresh_from_db()
        self.assertEqual(derivacion.estado, EstadoDerivacion.VISTA)
        self.assertIsNotNone(derivacion.vista_en)

        self.assertTrue(
            LogAcceso.objects.filter(
                usuario=self.user_b,
                accion='ver',
                modelo='Derivacion',
                objeto_id=derivacion.pk,
                detalle__contains='marcada como vista',
            ).exists()
        )

    def test_la_derivacion_vista_sigue_dando_acceso(self):
        derivacion = self.crear_derivacion()
        derivacion.estado = EstadoDerivacion.VISTA
        derivacion.vista_en = timezone.now()
        derivacion.save(update_fields=['estado', 'vista_en'])

        self.login(self.user_b)
        self.assertEqual(
            self.client.get(
                reverse('pacientes:detalle', args=[self.paciente.pk])
            ).status_code,
            200,
        )


class CancelacionDerivacionTests(BaseDerivacionesTests):
    def test_cancelacion_revoca_el_acceso(self):
        derivacion = self.crear_derivacion()
        self.login(self.user_a)

        response = self.client.post(
            reverse('derivaciones:cancelar', args=[derivacion.pk]),
        )
        self.assertRedirects(
            response,
            reverse('derivaciones:detalle', args=[derivacion.pk]),
        )

        derivacion.refresh_from_db()
        self.assertEqual(derivacion.estado, EstadoDerivacion.CANCELADA)

        solicitud = derivacion.solicitud_turno
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, EstadoSolicitud.DESCARTADA)

        self.assertTrue(
            LogAcceso.objects.filter(
                usuario=self.user_a,
                accion='editar',
                modelo='Derivacion',
                objeto_id=derivacion.pk,
                detalle__contains='cancelada',
            ).exists()
        )

        # El destino pierde el acceso a la ficha y al PDF.
        self.login(self.user_b)
        self.assertEqual(
            self.client.get(
                reverse('pacientes:detalle', args=[self.paciente.pk])
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                reverse('pacientes:descargar_pdf', args=[self.paciente.pk])
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                reverse('historias:nueva_nota', args=[self.paciente.pk]),
                {'texto': 'Sin acceso tras cancelar.'},
            ).status_code,
            404,
        )

        # El tercero sigue sin acceso.
        self.login(self.user_c)
        self.assertEqual(
            self.client.get(
                reverse('pacientes:detalle', args=[self.paciente.pk])
            ).status_code,
            404,
        )

    def test_solo_el_origen_puede_cancelar(self):
        derivacion = self.crear_derivacion()

        for usuario in (self.user_b, self.user_c, self.recepcion):
            with self.subTest(usuario=usuario.username):
                self.login(usuario)
                response = self.client.post(
                    reverse(
                        'derivaciones:cancelar',
                        args=[derivacion.pk],
                    )
                )
                self.assertEqual(response.status_code, 403)

        derivacion.refresh_from_db()
        self.assertEqual(derivacion.estado, EstadoDerivacion.PENDIENTE)

    def test_no_se_puede_cancelar_una_derivacion_vista(self):
        derivacion = self.crear_derivacion()
        derivacion.estado = EstadoDerivacion.VISTA
        derivacion.vista_en = timezone.now()
        derivacion.save(update_fields=['estado', 'vista_en'])

        self.login(self.user_a)
        response = self.client.post(
            reverse('derivaciones:cancelar', args=[derivacion.pk]),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        derivacion.refresh_from_db()
        self.assertEqual(derivacion.estado, EstadoDerivacion.VISTA)


class BandejaYContadoresTests(BaseDerivacionesTests):
    def test_contador_de_pendientes_para_el_destino(self):
        self.crear_derivacion()
        self.crear_derivacion(
            paciente=self.paciente_c,
            motivo='Otra derivación.',
        )
        vista = self.crear_derivacion(
            paciente=self.paciente,
            destino=self.prof_sin_usuario,
        )
        vista.estado = EstadoDerivacion.VISTA
        vista.vista_en = timezone.now()
        vista.save(update_fields=['estado', 'vista_en'])

        factory = RequestFactory()

        request = factory.get('/')
        request.user = self.user_b
        self.assertEqual(roles(request)['derivaciones_pendientes_count'], 2)

        request = factory.get('/')
        request.user = self.user_a
        self.assertEqual(roles(request)['derivaciones_pendientes_count'], 0)

        request = factory.get('/')
        request.user = self.recepcion
        self.assertEqual(roles(request)['derivaciones_pendientes_count'], 0)

        request = factory.get('/')
        request.user = self.admin
        self.assertEqual(roles(request)['derivaciones_pendientes_count'], 0)

        request = factory.get('/')
        request.user = AnonymousUser()
        self.assertEqual(roles(request)['derivaciones_pendientes_count'], 0)

    def test_menu_y_tarjeta_del_dashboard_para_el_destino(self):
        self.crear_derivacion(motivo='Derivación visible en dashboard.')

        self.login(self.user_b)
        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Derivaciones pendientes')
        self.assertContains(response, 'title="Derivaciones pendientes"')
        # La tarjeta del dashboard resume paciente, origen y fecha.
        self.assertContains(response, self.paciente.apellido)
        self.assertContains(response, f'De {self.prof_a}')
        self.assertContains(response, 'Nueva')

        self.login(self.user_a)
        response = self.client.get(reverse('dashboard:index'))
        self.assertContains(response, 'Derivaciones')
        self.assertNotContains(response, 'title="Derivaciones pendientes"')
        self.assertContains(response, 'No tenés derivaciones pendientes.')

    def test_pestanas_recibidas_y_enviadas(self):
        recibida = self.crear_derivacion(motivo='Recibida por B.')
        enviada = self.crear_derivacion(
            paciente=self.paciente_c,
            origen=self.prof_b,
            destino=self.prof_c,
            motivo='Enviada por B.',
        )

        self.login(self.user_b)
        response = self.client.get(
            reverse('derivaciones:lista'),
            {'tab': 'recibidas'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Recibida por B.')
        self.assertNotContains(response, 'Enviada por B.')
        self.assertEqual(response.context['recibidas'], 1)
        self.assertEqual(response.context['enviadas'], 1)
        self.assertEqual(response.context['pendientes'], 1)

        response = self.client.get(
            reverse('derivaciones:lista'),
            {'tab': 'enviadas'},
        )
        self.assertContains(response, 'Enviada por B.')
        self.assertNotContains(response, 'Recibida por B.')

        # El origen ve la derivación en su bandeja de enviadas.
        self.login(self.user_a)
        response = self.client.get(
            reverse('derivaciones:lista'),
            {'tab': 'enviadas'},
        )
        self.assertContains(response, 'Recibida por B.')

        # El tercero no ve derivaciones de otros.
        self.login(self.user_c)
        response = self.client.get(reverse('derivaciones:lista'))
        self.assertNotContains(response, 'Recibida por B.')

        # Recepción ve todo en modo lectura.
        self.login(self.recepcion)
        response = self.client.get(reverse('derivaciones:lista'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Recibida por B.')
        self.assertContains(response, 'Enviada por B.')
        self.assertContains(response, 'solo lectura')

    def test_ficha_muestra_cartel_y_boton_de_derivar(self):
        derivacion = self.crear_derivacion()

        self.login(self.user_b)
        response = self.client.get(
            reverse('pacientes:detalle', args=[self.paciente.pk])
        )
        self.assertContains(
            response,
            reverse('derivaciones:crear', args=[self.paciente.pk]),
        )
        self.assertContains(response, 'Derivado por')
        self.assertContains(response, derivacion.motivo)
        self.assertContains(
            response,
            timezone.localtime(derivacion.creado).strftime('%d/%m/%Y'),
        )

        self.login(self.user_a)
        response = self.client.get(
            reverse('pacientes:detalle', args=[self.paciente.pk])
        )
        self.assertContains(response, 'Derivar paciente')
        self.assertNotContains(response, 'Derivado por')

        self.login(self.recepcion)
        response = self.client.get(
            reverse('pacientes:detalle', args=[self.paciente.pk])
        )
        self.assertNotContains(response, 'Derivar paciente')

    def test_busqueda_de_profesionales_excluye_al_origen(self):
        self.login(self.user_a)
        response = self.client.get(
            reverse('derivaciones:buscar_profesionales'),
            {'q': 'Derivaciones'},
        )
        self.assertEqual(response.status_code, 200)
        resultados = {item['id']: item for item in response.json()['results']}

        self.assertNotIn(self.prof_a.pk, resultados)
        self.assertTrue(resultados[self.prof_b.pk]['tiene_usuario'])
        self.assertFalse(
            resultados[self.prof_sin_usuario.pk]['tiene_usuario']
        )

        self.client.logout()
        response = self.client.get(
            reverse('derivaciones:buscar_profesionales')
        )
        self.assertEqual(response.status_code, 302)


class PermisosBandejaTests(BaseDerivacionesTests):
    def test_derivacion_solo_visible_para_origen_destino_y_recepcion(self):
        derivacion = self.crear_derivacion()
        url = reverse('derivaciones:detalle', args=[derivacion.pk])

        self.login(self.user_a)
        self.assertEqual(self.client.get(url).status_code, 200)

        self.login(self.user_b)
        self.assertEqual(self.client.get(url).status_code, 200)

        self.login(self.user_c)
        self.assertEqual(self.client.get(url).status_code, 404)

        self.login(self.recepcion)
        self.assertEqual(self.client.get(url).status_code, 200)

        self.login(self.admin)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_anonimo_redirige_al_login(self):
        derivacion = self.crear_derivacion()
        response = self.client.get(
            reverse('derivaciones:detalle', args=[derivacion.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

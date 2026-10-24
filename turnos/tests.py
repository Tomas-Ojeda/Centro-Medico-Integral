from datetime import date

from django.contrib.auth.models import User
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from historias.models import Consulta
from pacientes.models import Paciente
from profesionales.models import Especialidad, Profesional
from .models import Turno


class TurnoEspecialidadTests(TestCase):
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
        self.fecha = self.fecha_hora.strftime('%Y-%m-%d')

    def datos_profesional(self, dni, especialidades=''):
        return {
            'nombre': 'Ana',
            'apellido': 'García',
            'dni': dni,
            'matricula_nacional': 'MP 1234',
            'matricula_provincial': '',
            'telefono': '',
            'email': f'{dni}@example.com',
            'fecha_ingreso': '2020-01-15',
            'activo': 'on',
            'especialidades': especialidades,
        }

    def crear_profesional(self, dni='30111222', especialidades=''):
        self.client.post(
            reverse('profesionales:crear'),
            self.datos_profesional(dni, especialidades),
        )
        return Profesional.objects.get(dni=dni)

    def editar_profesional(self, profesional, especialidades):
        self.client.post(
            reverse('profesionales:editar', args=[profesional.pk]),
            self.datos_profesional(profesional.dni, especialidades),
        )

    def crear_turno(self, profesional):
        return self.client.post(
            reverse('turnos:crear'),
            {
                'paciente': self.paciente.pk,
                'profesional': profesional.pk,
                'fecha_hora': self.fecha_hora.strftime('%Y-%m-%dT%H:%M'),
                'motivo': 'Control',
                'estado': 'pendiente',
                'observaciones': '',
            },
        )

    def test_turno_creado_sin_especialidad_muestra_la_actual_en_agenda(self):
        profesional = self.crear_profesional()
        self.assertEqual(self.crear_turno(profesional).status_code, 302)

        self.editar_profesional(profesional, 'Cardiología')

        response = self.client.get(
            reverse('turnos:agenda'),
            {'fecha': self.fecha},
        )
        self.assertContains(response, '🩺 Cardiología')

        response = self.client.get(
            reverse('turnos:agenda'),
            {'fecha': self.fecha, 'especialidad': 'Cardiología'},
        )
        self.assertContains(response, self.paciente.apellido)

    def test_turno_creado_sin_especialidad_luego_dos_se_ven_y_filtran(self):
        profesional = self.crear_profesional()
        self.crear_turno(profesional)
        self.editar_profesional(profesional, 'Cardiología, Clínica Médica')

        response = self.client.get(
            reverse('turnos:agenda'),
            {'fecha': self.fecha},
        )
        self.assertContains(response, '🩺 Cardiología, Clínica Médica')

        for especialidad in ('Cardiología', 'Clínica Médica'):
            response = self.client.get(
                reverse('turnos:agenda'),
                {'fecha': self.fecha, 'especialidad': especialidad},
            )
            self.assertContains(response, self.paciente.apellido)

    def test_agenda_filtra_por_cada_especialidad_del_profesional(self):
        profesional = self.crear_profesional(
            especialidades='Cardiología, Clínica Médica',
        )
        self.crear_turno(profesional)

        for especialidad in ('Cardiología', 'Clínica Médica'):
            response = self.client.get(
                reverse('turnos:agenda'),
                {'fecha': self.fecha, 'especialidad': especialidad},
            )
            self.assertContains(response, self.paciente.apellido)

    def test_agenda_no_trunca_especialidades_multiples(self):
        profesional = self.crear_profesional(
            especialidades='Endocrinología Pediátrica, Gastroenterología Infantil',
        )
        self.crear_turno(profesional)

        response = self.client.get(
            reverse('turnos:agenda'),
            {'fecha': self.fecha},
        )
        self.assertContains(
            response,
            '🩺 Endocrinología Pediátrica, Gastroenterología Infantil',
        )

    def test_csv_exporta_especialidad_actual_del_profesional(self):
        profesional = self.crear_profesional(especialidades='Cardiología')
        self.crear_turno(profesional)
        self.editar_profesional(profesional, 'Cardiología, Clínica Médica')

        response = self.client.get(
            reverse('turnos:exportar_csv'),
            {'fecha': self.fecha},
        )
        contenido = response.content.decode('utf-8-sig')
        self.assertIn('Cardiología, Clínica Médica', contenido)

    def test_calendario_muestra_especialidad_actual_del_profesional(self):
        profesional = self.crear_profesional(especialidades='Cardiología')
        self.crear_turno(profesional)
        self.editar_profesional(profesional, 'Cardiología, Clínica Médica')

        response = self.client.get(
            reverse('turnos:agenda'),
            {'fecha': self.fecha, 'vista': 'calendario'},
        )
        self.assertContains(response, 'Cardiología, Clínica Médica')


class MigracionEspecialidadesTests(TransactionTestCase):
    migrate_from = [
        ('turnos', '0001_initial'),
        ('historias', '0003_alter_consulta_archivo_adjunto'),
        ('pacientes', '0002_alter_paciente_obra_social'),
        (
            'profesionales',
            '0002_especialidad_remove_profesional_especialidad_and_more',
        ),
    ]
    migrate_to = [
        ('turnos', '0002_completar_especialidad_turno'),
        ('historias', '0004_completar_especialidad_consulta'),
        ('pacientes', '0002_alter_paciente_obra_social'),
        (
            'profesionales',
            '0002_especialidad_remove_profesional_especialidad_and_more',
        ),
    ]

    def setUp(self):
        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.migrate_from)
        apps_viejas = self.executor.loader.project_state(self.migrate_from).apps

        PacienteViejo = apps_viejas.get_model('pacientes', 'Paciente')
        ProfesionalViejo = apps_viejas.get_model('profesionales', 'Profesional')
        EspecialidadVieja = apps_viejas.get_model('profesionales', 'Especialidad')
        TurnoViejo = apps_viejas.get_model('turnos', 'Turno')
        ConsultaVieja = apps_viejas.get_model('historias', 'Consulta')

        paciente = PacienteViejo.objects.create(
            dni='30111222',
            nombre='Ana',
            apellido='Pérez',
            fecha_nacimiento=date(1985, 4, 12),
        )
        profesional = ProfesionalViejo.objects.create(
            nombre='Ana',
            apellido='García',
            dni='30111223',
            fecha_ingreso=date(2020, 1, 15),
        )
        especialidad = EspecialidadVieja.objects.create(nombre='Cardiología')
        profesional.especialidades.add(especialidad)

        fecha_hora = timezone.now()
        self.turno = TurnoViejo.objects.create(
            paciente=paciente,
            profesional=profesional,
            fecha_hora=fecha_hora,
            especialidad='',
            motivo='Control',
        )
        self.turno_historico = TurnoViejo.objects.create(
            paciente=paciente,
            profesional=profesional,
            fecha_hora=fecha_hora,
            especialidad='Texto histórico',
            motivo='Control',
        )
        self.turno_editado = TurnoViejo.objects.create(
            paciente=paciente,
            profesional=profesional,
            fecha_hora=fecha_hora,
            especialidad='',
            motivo='Control',
        )
        self.consulta = ConsultaVieja.objects.create(
            paciente=paciente,
            profesional=profesional,
            fecha_hora=fecha_hora,
            especialidad='',
            diagnostico='Control general',
        )
        self.consulta_historica = ConsultaVieja.objects.create(
            paciente=paciente,
            profesional=profesional,
            fecha_hora=fecha_hora,
            especialidad='Texto histórico',
            diagnostico='Control general',
        )
        self.consulta_editada = ConsultaVieja.objects.create(
            paciente=paciente,
            profesional=profesional,
            fecha_hora=fecha_hora,
            especialidad='',
            diagnostico='Control general',
        )

        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.migrate_to)

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_completa_vacios_y_respeta_textos_historicos(self):
        self.turno.refresh_from_db()
        self.turno_historico.refresh_from_db()
        self.turno_editado.refresh_from_db()
        self.consulta.refresh_from_db()
        self.consulta_historica.refresh_from_db()
        self.consulta_editada.refresh_from_db()

        self.assertEqual(self.turno.especialidad, 'Cardiología')
        self.assertEqual(self.turno_editado.especialidad, 'Cardiología')
        self.assertEqual(self.turno_historico.especialidad, 'Texto histórico')

        self.assertEqual(self.consulta.especialidad, 'Cardiología')
        self.assertEqual(self.consulta_editada.especialidad, 'Cardiología')
        self.assertEqual(self.consulta_historica.especialidad, 'Texto histórico')

    def test_revertir_restaura_solo_los_completados_sin_editar(self):
        Turno.objects.filter(pk=self.turno_editado.pk).update(
            especialidad='Editada después',
        )
        Consulta.objects.filter(pk=self.consulta_editada.pk).update(
            especialidad='Editada después',
        )

        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.migrate_from)

        self.turno.refresh_from_db()
        self.turno_historico.refresh_from_db()
        self.turno_editado.refresh_from_db()
        self.consulta.refresh_from_db()
        self.consulta_historica.refresh_from_db()
        self.consulta_editada.refresh_from_db()

        self.assertEqual(self.turno.especialidad, '')
        self.assertEqual(self.turno_editado.especialidad, 'Editada después')
        self.assertEqual(self.turno_historico.especialidad, 'Texto histórico')

        self.assertEqual(self.consulta.especialidad, '')
        self.assertEqual(self.consulta_editada.especialidad, 'Editada después')
        self.assertEqual(self.consulta_historica.especialidad, 'Texto histórico')

        tablas = connection.introspection.table_names()
        self.assertNotIn('_migracion_turno_especialidad', tablas)
        self.assertNotIn('_migracion_consulta_especialidad', tablas)

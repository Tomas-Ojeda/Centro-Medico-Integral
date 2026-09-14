#!/usr/bin/env python
"""
Script de carga de datos iniciales para Centro Médico Integral.
Uso: python seed_data.py

Crea:
  - 1 usuario administrador (admin / admin123)
  - 6 profesionales con distintas especialidades
  - 8 pacientes con datos completos
  - Turnos para los próximos días
  - Historial clínico con consultas de ejemplo
"""
import os
import sys
import django
from datetime import date, timedelta, datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'consultorio_salto.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.contrib.auth.models import User
from pacientes.models import Paciente
from profesionales.models import Profesional
from turnos.models import Turno, EstadoTurno
from historias.models import Consulta
from django.utils import timezone


def run():
    print("🚀 Iniciando carga de datos...")

    # ── USUARIO ADMIN ──────────────────────────────────────────
    if not User.objects.filter(username='tomijeroj941').exists():
        User.objects.create_superuser('tomijeroj941', 'admin@centromedico.com', 'admin123')
        print("  ✅ Usuario admin creado: tomijeroj941 / admin123")
    else:
        print("  ℹ️  Usuario admin ya existe.")

    # ── PROFESIONALES ──────────────────────────────────────────
    profs_data = [
        dict(nombre='Agustin', apellido='Olivares', dni='20111222', matricula_nacional='12344',
             matricula_provincial='312412', especialidad='Kinesiología', telefono='123141243',
             email='jkjflakfja2@gmail.com', fecha_ingreso=date(2020, 3, 1)),
        dict(nombre='Sol', apellido='Miralla', dni='27334455', matricula_nacional='1234',
             matricula_provincial='4123', especialidad='Odontología', telefono='02604334973',
             email='nati1bayon@gmail.com', fecha_ingreso=date(2019, 6, 15)),
        dict(nombre='Lucia', apellido='Castaño', dni='32556677', matricula_nacional='67897',
             matricula_provincial='5463', especialidad='Psicología', telefono='2604786950',
             email='castanolucia21@gmail.com', fecha_ingreso=date(2021, 1, 10)),
        dict(nombre='Santiago', apellido='Pereira', dni='25778899', matricula_nacional='9950',
             matricula_provincial='5434', especialidad='Neurología', telefono='2604589533',
             email='santipereira99@gmail.com', fecha_ingreso=date(2018, 9, 5)),
        dict(nombre='Lorena', apellido='Cabrera', dni='28990011', matricula_nacional='11244',
             matricula_provincial='2334', especialidad='Ginecología', telefono='2604345432',
             email='lorecabrera12@gmail.com', fecha_ingreso=date(2022, 4, 20)),
        dict(nombre='Esteban', apellido='Casares', dni='30112233', matricula_nacional='231',
             matricula_provincial='321', especialidad='Pediatría', telefono='02604684067',
             email='estebCasares@gmail.com', fecha_ingreso=date(2017, 11, 1)),
        dict(nombre='Patricia', apellido='Alonso', dni='26445566', matricula_nacional='55123',
             matricula_provincial='8901', especialidad='Cardiología', telefono='2604123456',
             email='patricialon@gmail.com', fecha_ingreso=date(2016, 2, 14)),
    ]

    profesionales = {}
    for d in profs_data:
        p, created = Profesional.objects.get_or_create(dni=d['dni'], defaults=d)
        profesionales[p.apellido] = p
        if created:
            print(f"  ✅ Profesional: {p}")

    # ── PACIENTES ──────────────────────────────────────────────
    pacientes_data = [
        dict(dni='30456789', nombre='María', apellido='González', fecha_nacimiento=date(1985, 3, 14),
             telefono='11-4567-8901', email='maria.gonzalez@email.com',
             direccion='Av. Corrientes 1234, CABA', obra_social='OSDE', numero_socio='1001'),
        dict(dni='12123433', nombre='Camila', apellido='Jamon', fecha_nacimiento=date(1992, 7, 22),
             telefono='2604-333444', email='camila.jamon@email.com',
             direccion='Rivadavia 567, Mendoza', obra_social='OSEP', numero_socio='1002'),
        dict(dni='25678901', nombre='Carlos', apellido='López', fecha_nacimiento=date(1978, 11, 5),
             telefono='2604-111222', email='carlos.lopez@email.com',
             direccion='San Martín 890, Mendoza', obra_social='OSDE', numero_socio='1003'),
        dict(dni='33456789', nombre='Laura', apellido='Martínez', fecha_nacimiento=date(2001, 4, 30),
             telefono='2604-444555', email='laura.martinez@email.com',
             direccion='Belgrano 234, Mendoza', obra_social='Medicus', numero_socio='1004'),
        dict(dni='12123123', nombre='Néstor', apellido='Ojeda', fecha_nacimiento=date(1965, 8, 18),
             telefono='2604-666777', email='nestor.ojeda@email.com',
             direccion='Mitre 456, Mendoza', obra_social='OSEP', numero_socio='1005'),
        dict(dni='28123456', nombre='Juan', apellido='Pérez', fecha_nacimiento=date(1990, 12, 3),
             telefono='2604-888999', email='juan.perez@email.com',
             direccion='Las Heras 789, Mendoza', obra_social='Swiss Medical', numero_socio='1006'),
        dict(dni='35678901', nombre='Ana', apellido='Rodríguez', fecha_nacimiento=date(2008, 5, 20),
             telefono='2604-222333', email='ana.rodriguez@email.com',
             direccion='Gral. Paz 101, Mendoza', obra_social='Galeno', numero_socio='1007'),
        dict(dni='22334455', nombre='Roberto', apellido='Fernández', fecha_nacimiento=date(1955, 2, 9),
             telefono='2604-000111', email='roberto.fernandez@email.com',
             direccion='Independencia 500, Mendoza', obra_social='Particular', numero_socio='1008'),
    ]

    pacientes = {}
    for d in pacientes_data:
        p, created = Paciente.objects.get_or_create(dni=d['dni'], defaults=d)
        pacientes[p.apellido] = p
        if created:
            print(f"  ✅ Paciente: {p}")

    # ── HISTORIAL CLÍNICO ──────────────────────────────────────
    hoy = timezone.now()
    consultas_data = [
        dict(
            paciente=pacientes['González'],
            profesional=profesionales['Alonso'],
            fecha_hora=hoy - timedelta(days=90),
            especialidad='Cardiología',
            motivo='Control cardiovascular anual',
            diagnostico='Tensión arterial levemente elevada',
            evolucion='Se indica monitoreo ambulatorio de presión arterial (MAPA). Dieta hiposódica.',
            tratamiento='Losartán 50mg/día. Control en 30 días.',
        ),
        dict(
            paciente=pacientes['González'],
            profesional=profesionales['Castaño'],
            fecha_hora=hoy - timedelta(days=30),
            especialidad='Psicología',
            motivo='Estrés laboral y dificultades para dormir',
            diagnostico='Trastorno adaptativo con ansiedad leve',
            evolucion='Paciente refiere mejoría parcial. Continúa con técnicas de relajación.',
            tratamiento='Sesiones semanales de psicoterapia cognitivo-conductual.',
        ),
        dict(
            paciente=pacientes['López'],
            profesional=profesionales['Pereira'],
            fecha_hora=hoy - timedelta(days=60),
            especialidad='Neurología',
            motivo='Cefaleas recurrentes',
            diagnostico='Migraña sin aura',
            evolucion='Se realizó RMN de cerebro sin contraste, resultado normal.',
            tratamiento='Ibuprofeno 600mg ante crisis. Evitar factores desencadenantes.',
        ),
        dict(
            paciente=pacientes['Ojeda'],
            profesional=profesionales['Casares'],
            fecha_hora=hoy - timedelta(days=15),
            especialidad='Pediatría',
            motivo='Control pediátrico y vacunación',
            diagnostico='Paciente en buen estado general',
            evolucion='Desarrollo acorde a la edad. Vacuna antigripal aplicada.',
            tratamiento='Próximo control en 6 meses.',
        ),
    ]

    for d in consultas_data:
        if not Consulta.objects.filter(paciente=d['paciente'], fecha_hora=d['fecha_hora']).exists():
            Consulta.objects.create(**d)
            print(f"  ✅ Consulta: {d['paciente']} — {d['diagnostico'][:40]}")

    # ── TURNOS ────────────────────────────────────────────────
    today = date.today()
    turnos_data = [
        dict(paciente=pacientes['González'], profesional=profesionales['Castaño'],
             fecha_hora=timezone.make_aware(datetime.combine(today, datetime.min.time().replace(hour=9))),
             especialidad='Psicología', motivo='Seguimiento terapéutico', estado='pendiente'),
        dict(paciente=pacientes['López'], profesional=profesionales['Pereira'],
             fecha_hora=timezone.make_aware(datetime.combine(today, datetime.min.time().replace(hour=10, minute=30))),
             especialidad='Neurología', motivo='Control migraña', estado='confirmado'),
        dict(paciente=pacientes['Martínez'], profesional=profesionales['Olivares'],
             fecha_hora=timezone.make_aware(datetime.combine(today + timedelta(days=1), datetime.min.time().replace(hour=11))),
             especialidad='Kinesiología', motivo='Rehabilitación rodilla', estado='pendiente'),
        dict(paciente=pacientes['Jamon'], profesional=profesionales['Miralla'],
             fecha_hora=timezone.make_aware(datetime.combine(today + timedelta(days=2), datetime.min.time().replace(hour=14))),
             especialidad='Odontología', motivo='Limpieza dental', estado='pendiente'),
        dict(paciente=pacientes['Pérez'], profesional=profesionales['Alonso'],
             fecha_hora=timezone.make_aware(datetime.combine(today + timedelta(days=3), datetime.min.time().replace(hour=9, minute=30))),
             especialidad='Cardiología', motivo='Primer control cardiovascular', estado='pendiente'),
        dict(paciente=pacientes['Fernández'], profesional=profesionales['Casares'],
             fecha_hora=timezone.make_aware(datetime.combine(today - timedelta(days=1), datetime.min.time().replace(hour=15))),
             especialidad='Pediatría', motivo='Control pediátrico', estado='realizado'),
    ]

    for d in turnos_data:
        if not Turno.objects.filter(paciente=d['paciente'], fecha_hora=d['fecha_hora']).exists():
            Turno.objects.create(**d)
            print(f"  ✅ Turno: {d['paciente']} — {d['fecha_hora'].strftime('%d/%m %H:%M')}")

    print("\n✨ ¡Datos cargados correctamente!")
    print("   Acceso: python manage.py runserver")
    print("   Usuario: tomijeroj941 | Contraseña: admin123")


if __name__ == '__main__':
    run()

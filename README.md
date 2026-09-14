# Centro Médico Integral 🏥

[![Python](https://img.shields.io/badge/Python-3.10+-3776ab?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-4.2+-092E20?style=flat-square&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-336791?style=flat-square&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Enabled-2496ED?style=flat-square&logo=docker&logoColor=white)](https://www.docker.com/)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-green?style=flat-square)](https://github.com/Tomas-Ojeda/Centro-Medico-Integral)

Sistema de gestión de pacientes, historias clínicas, profesionales y turnos para centros médicos en Argentina.

## Características

- **Gestión de pacientes** con datos de salud encriptados (Ley 25326)
- **Historias clínicas digitales** con fotos procesadas por IA (Claude Vision)
- **Agenda de turnos** con validación de disponibilidad
- **Profesionales** con especialidades
- **Importación masiva** desde Excel/CSV
- **Auditoría completa** de accesos (logs)
- **HTTPS** en producción, con Railway
- **Docker Compose** para deploy simple

## Stack

- **Backend:** Django 4.2 + PostgreSQL
- **Contenedores:** Docker + Nginx
- **IA:** Anthropic API (Claude Vision)
- **Seguridad:** Role-based access control, Ley 25326 compliance

## Requisitos legales

✅ Cumple Ley 25326 (Protección de Datos Personales)  
✅ Cumple Ley 26388 (Delitos Informáticos)  
✅ Requiere inscripción en RNBD antes de uso  

## Instalación local

### Requisitos
- Docker & Docker Compose
- Python 3.10+
- Git

### Pasos

```bash
git clone https://github.com/TU_USUARIO/centro-medico-integral.git
cd centro-medico-integral

# Crear .env desde el template
cp .env.example .env
# ← Editar .env con tus valores

docker-compose up -d
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py createsuperuser
```

Acceder en `https://localhost`

## Licencia

⚠️ Propiedad intelectual reservada. Solo uso en clientes autorizados.
# Centro Médico Integral 🏥

[![Python](https://img.shields.io/badge/Python-3.13+-3776ab?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.2+-092E20?style=flat-square&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+-336791?style=flat-square&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Enabled-2496ED?style=flat-square&logo=docker&logoColor=white)](https://www.docker.com/)
[![Security](https://img.shields.io/badge/Security-Hardened-green?style=flat-square)](https://github.com/Tomas-Ojeda/Centro-Medico-Integral)

Sistema de gestión de pacientes, historias clínicas, profesionales y turnos para centros médicos en Argentina.

## Características

- **Gestión de pacientes** con datos protegidos (Ley 25326)
- **Historias clínicas digitales** con archivos adjuntos validados
- **Agenda de turnos** con calendario mensual y exportación CSV
- **Profesionales** con especialidades y matrículas
- **Importación masiva** desde Excel, CSV o fotos de planillas (IA)
- **Generación de PDF** con historia clínica completa
- **Auditoría de accesos** — registro de quién vio qué, cuándo y desde qué IP
- **Bloqueo de fuerza bruta** (django-axes) — 5 intentos fallidos = 15 min de bloqueo
- **Archivos adjuntos protegidos** — solo accesibles por usuarios autenticados
- **Validación de archivos** — extensión, tipo MIME real y tamaño máximo (10 MB)
- **Nombres aleatorios** para archivos subidos (UUID)

## Stack

- **Backend:** Django 5.2 + PostgreSQL 16
- **Contenedores:** Docker + Nginx
- **IA:** Anthropic API (Claude Vision) para importación de planillas
- **Seguridad:** HSTS, cookies seguras, django-axes, auditoría de accesos
- **Static files:** WhiteNoise

## Seguridad

| Medida | Descripción |
|--------|-------------|
| Secretos fuera del código | `SECRET_KEY` y `ANTHROPIC_API_KEY` se leen de variables de entorno |
| Media protegida | Archivos adjuntos solo servidos por vistas autenticadas |
| Validación de archivos | Extensión + MIME real + tamaño máximo |
| HSTS | HTTP Strict Transport Security (1 año) |
| Cookies seguras | HttpOnly, Secure, SameSite=Lax |
| Bloqueo de fuerza bruta | django-axes (5 intentos = 15 min) |
| Auditoría | Registro de accesos (ver, crear, editar, borrar, descargar, exportar, importar, login) |
| Path traversal | Validación de rutas resuletas dentro de MEDIA_ROOT |

## Requisitos legales

- Ley 25326 (Protección de Datos Personales)
- Ley 26388 (Delitos Informáticos)
- Los datos de salud son sensibles — se requiere consentimiento del paciente

## Instalación local

### Requisitos
- Docker & Docker Compose
- Python 3.13+
- Git

### Pasos

```bash
git clone https://github.com/Tomas-Ojeda/Centro-Medico-Integral.git
cd Centro-Medico-Integral

# Crear .env desde el template
cp .env.example .env
# ← Editar .env con tus valores

docker-compose up -d
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py createsuperuser
```

Acceder en `http://localhost`

## Variables de entorno

| Variable | Descripción |
|----------|-------------|
| `DJANGO_SECRET_KEY` | Clave secreta de Django (obligatoria) |
| `DJANGO_DEBUG` | Modo debug (True/False) |
| `DJANGO_ALLOWED_HOSTS` | Hosts permitidos (separados por coma) |
| `ANTHROPIC_API_KEY` | API key de Anthropic (para importación con IA) |
| `SESSION_COOKIE_SECURE` | Cookies seguras (True en producción) |
| `CSRF_COOKIE_SECURE` | CSRF cookie segura (True en producción) |
| `SECURE_SSL_REDIRECT` | Redirigir HTTP a HTTPS (True en producción) |
| `SESSION_COOKIE_AGE` | Duración de sesión en segundos (default: 3600) |
| `ADMIN_URL` | Ruta del admin (default: admin/) |
| `DB_NAME` | Nombre de la base de datos PostgreSQL |
| `DB_USER` | Usuario de PostgreSQL |
| `DB_PASSWORD` | Contraseña de PostgreSQL |
| `PGADMIN_EMAIL` | Email de pgAdmin (solo desarrollo) |
| `PGADMIN_PASSWORD` | Contraseña de pgAdmin (solo desarrollo) |

## Despliegue en Render

1. Crear servicio web en Render con el repositorio
2. Configurar variables de entorno (ver tabla arriba)
3. `DJANGO_SETTINGS_MODULE=consultorio_salto.settings_prod`
4. Comando de inicio: `gunicorn consultorio_salto.wsgi:application --bind 0.0.0.0:$PORT`

## Estructura del proyecto

```
centro_medico_v2/
├── consultorio_salto/          # Configuración principal
│   ├── settings.py             # Settings de desarrollo
│   ├── settings_prod.py        # Settings de producción
│   └── urls.py
├── dashboard/                  # Panel principal
├── pacientes/                  # Gestión de pacientes
├── profesionales/              # Gestión de profesionales
├── turnos/                     # Agenda de turnos
├── historias/                  # Historias clínicas
├── auditoria/                  # Auditoría de accesos
├── docker/                     # Configuración Docker
├── templates/                  # Templates HTML
├── static/                     # Archivos estáticos
└── media/                      # Archivos subidos (protegidos)
```

## Licencia

Propiedad intelectual reservada. Uso autorizado únicamente.

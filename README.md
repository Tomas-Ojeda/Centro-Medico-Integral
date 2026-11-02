# Consultorios Médicos - Salto de las Rosas 🏥

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
- **Respaldo de adjuntos** — ZIP en streaming, solo para superusuarios
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

## Roles y permisos

El sistema usa tres roles:

| Rol | Cómo se asigna | Alcance |
|-----|----------------|---------|
| **Administrador** | Superusuario de Django | Acceso total, incluido `/admin` y eliminación de derivaciones |
| **Recepción** | Grupo `Recepcion` | Pacientes, turnos, profesionales e historias |
| **Profesional** | Grupo `Profesional` + vínculo con un `Profesional` | Solo sus pacientes, sus turnos y sus consultas |

La migración de roles agrega automáticamente al grupo `Recepcion` a todos los
usuarios existentes que no sean superusuarios, para no quitarles acceso al
desplegar. Un usuario sin ninguno de los dos grupos recibe una página de
acceso denegado.

### Crear un usuario profesional

1. Ingresar a `/admin` con un superusuario.
2. Ir a **Autenticación y autorización → Usuarios → Agregar usuario**.
3. Crear el usuario con su nombre de usuario y contraseña.
4. En la ficha del usuario, asignarle el grupo **`Profesional`**.
5. Ir a **Profesionales**, abrir la ficha del profesional correspondiente y
   seleccionar ese usuario en el campo **Usuario de acceso**. Guardar.
6. Si el usuario profesional no está vinculado a un profesional, al iniciar
   sesión verá el mensaje: *"Tu usuario no está vinculado a un profesional,
   contactá a recepción."*

Para un usuario de recepción, alcanza con asignarle el grupo **`Recepcion`**;
no hace falta vincularlo a un profesional.

> La vinculación `Profesional ↔ Usuario` se administra únicamente desde el
> admin de Django. No se expone en los formularios de recepción.

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

| Variable | Obligatoria | Descripción |
|----------|-------------|-------------|
| `DJANGO_SECRET_KEY` | Sí | Clave secreta de Django |
| `DJANGO_SETTINGS_MODULE` | Producción | `consultorio_salto.settings_prod` (el `Dockerfile` ya lo define) |
| `DJANGO_DEBUG` | No | `False` en producción (default: `True`) |
| `DJANGO_ALLOWED_HOSTS` | Sí | Hosts permitidos, separados por coma |
| `DATABASE_URL` | Producción | Render la inyecta automáticamente. En local se usa SQLite |
| `MEDIA_ROOT` | Producción | Ruta de los adjuntos. En Render: `/var/data/media` (default local: `BASE_DIR/media`) |
| `ANTHROPIC_API_KEY` | Para IA | API key de Anthropic (importación de planillas) |
| `SESSION_COOKIE_SECURE` | No | Cookies seguras (`True` en producción con HTTPS) |
| `CSRF_COOKIE_SECURE` | No | CSRF cookie segura (`True` en producción con HTTPS) |
| `SECURE_SSL_REDIRECT` | No | Redirigir HTTP a HTTPS (`True` en producción) |
| `SESSION_COOKIE_AGE` | No | Duración de sesión en segundos (default: 3600) |
| `ADMIN_URL` | No | Ruta del admin (default: `admin/`) |
| `NOTAS_VISIBLES_PARA_RECEPCION` | No | `True`/`False` (default: `True`) |
| `PAGOS_VISIBLES_PARA_PROFESIONAL` | No | `True`/`False` (default: `False`) |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST` | Solo Docker local | Conexión a PostgreSQL del `docker-compose.yml` |
| `PGADMIN_EMAIL`, `PGADMIN_PASSWORD` | Solo desarrollo | Acceso a pgAdmin local |

## Despliegue en Render

El servicio real es un **Web Service Docker** (no usa el runtime Python nativo):

- **Runtime:** Docker, construido con `Dockerfile`; el arranque lo maneja
  `docker/entrypoint.sh`.
- **Plan:** Starter / 0.5 CPU / 512 MB RAM, **1 instancia**.
- **Disco persistente:** 1 GB montado en `/var/data/media`.
  `MEDIA_ROOT=/var/data/media`. No se guarda nada fuera de esa ruta.
- **Base de datos:** PostgreSQL de Render (0.1 CPU / 256 MB RAM, 1 GB de disco).
- **Migraciones:** en **cada arranque** el entrypoint ejecuta
  `python manage.py migrate --noinput` y
  `python manage.py collectstatic --noinput --clear` antes de iniciar Gunicorn
  con 3 workers. No hay que correr migraciones a mano después de un deploy.
- **Variables obligatorias:** `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False`,
  `DJANGO_ALLOWED_HOSTS`, `DATABASE_URL` (la inyecta Render) y
  `MEDIA_ROOT=/var/data/media`. `DJANGO_SETTINGS_MODULE` ya viene definida en
  el `Dockerfile`.
- `render.yaml` queda como **archivo de referencia**: la configuración vigente
  se administra desde el dashboard. No sincronices el Blueprint sin comparar
  antes planes, disco y variables.

### Respaldo de adjuntos

Los adjuntos de historia clínica viven en el disco persistente. Para descargar
un respaldo completo:

1. Ingresar como **superusuario**.
2. Abrir `/admin-tools/respaldo-adjuntos/`.
3. Se descarga `respaldo_adjuntos_AAAAMMDD_HHMMSS.zip` con todo el contenido de
   `MEDIA_ROOT` (la carpeta `historias_clinicas/` y lo que haya dentro).
4. Guardar el `.zip` fuera de Render (pendrive, disco externo o nube privada).

La vista arma el ZIP en un archivo temporal y lo envía en streaming, así no
carga los adjuntos en memoria. El temporal se escribe en `/tmp` del contenedor
(disco efímero), no en el disco persistente. Cada descarga queda registrada en
Auditoría con la acción `descargar` y el modelo `RespaldoAdjuntos`.

El disco es de **1 GB**: verificá el espacio disponible antes de generar
respaldos muy grandes. Para la base de datos, usá los backups automáticos del
plan de Render si están disponibles y además descargá un dump periódico con
`pg_dump` desde una máquina con acceso a la base. Guardá base y adjuntos juntos,
con la misma fecha.

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
├── admin_tools/                # Herramientas de administración (respaldos)
├── docker/                     # Configuración Docker
├── templates/                  # Templates HTML
├── static/                     # Archivos estáticos
└── media/                      # Archivos subidos (protegidos)
```

## Licencia

Propiedad intelectual reservada. Uso autorizado únicamente.

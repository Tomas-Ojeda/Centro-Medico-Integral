import os
from datetime import timedelta
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# ─── Identidad del centro ───────────────────────────────────────
NOMBRE_CENTRO = 'Consultorios Médicos - Salto de las Rosas'
NOMBRE_CENTRO_TITULO = 'Consultorios Médicos'
NOMBRE_CENTRO_LOCALIDAD = 'Salto de las Rosas'

# ─── Seguridad (leer de variables de entorno) ───────────────────
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    raise ImproperlyConfigured(
        'La variable de entorno DJANGO_SECRET_KEY no está definida. '
        'Generá una clave segura con: python -c "import secrets; print(secrets.token_urlsafe(50))"'
    )

DEBUG = os.environ.get('DJANGO_DEBUG', 'True') == 'True'
ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# Cookies seguras (activar en producción con HTTPS)
SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False') == 'True'
CSRF_COOKIE_SECURE = os.environ.get('CSRF_COOKIE_SECURE', 'False') == 'True'
SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', 'False') == 'True'

# Expiración de sesión (1 hora por defecto)
SESSION_COOKIE_AGE = int(os.environ.get('SESSION_COOKIE_AGE', '3600'))
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'axes',  # Bloqueo de intentos de login fallidos
    # App del proyecto (contiene el backend de login y comandos de gestión)
    'consultorio_salto',
    # Apps del proyecto
    'dashboard',
    'pacientes',
    'profesionales',
    'turnos',
    'derivaciones',
    'historias',
    'auditoria',
    'preferencias',
    'admin_tools',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'consultorio_salto.middleware.RolRequeridoMiddleware',
    'axes.middleware.AxesMiddleware',  # Debe ir después de AuthenticationMiddleware
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'consultorio_salto.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'consultorio_salto.context_processors.nombre_centro',
                'consultorio_salto.context_processors.roles',
                'preferencias.context_processors.paleta_usuario',
            ],
        },
    },
]

WSGI_APPLICATION = 'consultorio_salto.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 12},
    },
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'es-ar'
TIME_ZONE = 'America/Argentina/Buenos_Aires'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
# Configurable para montar un Persistent Disk en producción.
MEDIA_ROOT = Path(os.environ.get('MEDIA_ROOT', str(BASE_DIR / 'media')))

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

# ─── django-axes: Bloqueo de fuerza bruta ──────────────────────
AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    # Reemplaza a ModelBackend y permite ingresar el usuario sin distinguir
    # mayúsculas de minúsculas.
    'consultorio_salto.auth_backends.CaseInsensitiveBackend',
]

# Se bloquea solo la combinación IP + usuario. Así, los equipos del consultorio
# que comparten la IP pública no se bloquean entre sí por los fallos de otra
# persona. El costo es que una misma IP puede probar muchos usuarios distintos;
# se compensa con contraseñas de 12 caracteres o más y, más adelante, con 2FA.
AXES_FAILURE_LIMIT = int(os.environ.get('AXES_FAILURE_LIMIT', '8'))
AXES_COOLOFF_TIME = timedelta(minutes=15)
AXES_LOCKOUT_PARAMETERS = [['ip_address', 'username']]
AXES_RESET_ON_SUCCESS = True  # Resetear contador al loguearse bien
AXES_HTTP_RESPONSE_CODE = 429
AXES_LOCKOUT_TEMPLATE = 'registration/bloqueado.html'  # Mismo estilo que el login

# Detección de IP detrás de proxies (Render + Cloudflare).
# El default no cambia el comportamiento actual. Si axes_list_attempts muestra
# una IP compartida o de Cloudflare, probar con AXES_IP_HEADERS=HTTP_TRUE_CLIENT_IP,
# HTTP_CF_CONNECTING_IP,HTTP_X_FORWARDED_FOR,REMOTE_ADDR (ver README).
AXES_IP_HEADERS = tuple(
    header.strip()
    for header in os.environ.get(
        'AXES_IP_HEADERS',
        'HTTP_X_FORWARDED_FOR,REMOTE_ADDR',
    ).split(',')
    if header.strip()
) or ('HTTP_X_FORWARDED_FOR', 'REMOTE_ADDR')
AXES_IPWARE_PROXY_COUNT = 1  # Render usa 1 proxy
AXES_IPWARE_META_PRECEDENCE_ORDER = AXES_IP_HEADERS

# ─── Importación de planillas ──────────────────────────────────
# La API key se lee de la variable de entorno ANTHROPIC_API_KEY
# (console.anthropic.com → API Keys)
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')

# ─── Anotaciones clínicas ──────────────────────────────────────
# Define si Recepción puede ver las anotaciones clínicas (y en el PDF).
# Los profesionales y el Admin siempre las ven.
NOTAS_VISIBLES_PARA_RECEPCION = (
    os.environ.get('NOTAS_VISIBLES_PARA_RECEPCION', 'True') == 'True'
)

# ─── Registro interno de pagos ─────────────────────────────────
# Los profesionales nunca pueden registrar pagos. Si esta opción es True
# pueden ver la insignia con la forma de pago y el monto en la agenda.
PAGOS_VISIBLES_PARA_PROFESIONAL = (
    os.environ.get('PAGOS_VISIBLES_PARA_PROFESIONAL', 'False') == 'True'
)

import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# ─── Identidad del centro ───────────────────────────────────────
NOMBRE_CENTRO = 'Consultorios Médicos - Salto de las Rosas'

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
    # Apps del proyecto
    'dashboard',
    'pacientes',
    'profesionales',
    'turnos',
    'historias',
    'auditoria',
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
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'es-ar'
TIME_ZONE = 'America/Argentina/Buenos_Aires'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

# ─── django-axes: Bloqueo de fuerza bruta ──────────────────────
AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
]
AXES_FAILURE_LIMIT = 5  # Intentos fallidos antes de bloquear
AXES_COOLOFF_TIME = 0.25  # 15 minutos de bloqueo
AXES_LOCKOUT_PARAMETERS = ['ip_address', 'username']
AXES_IPWARE_PROXY_COUNT = 1  # Render usa 1 proxy
AXES_IPWARE_META_PRECEDENCE_ORDER = ('HTTP_X_FORWARDED_FOR', 'REMOTE_ADDR')
AXES_RESET_ON_SUCCESS = True  # Resetear contador al loguearse bien

# ─── Importación de planillas ──────────────────────────────────
# La API key se lee de la variable de entorno ANTHROPIC_API_KEY
# (console.anthropic.com → API Keys)
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')

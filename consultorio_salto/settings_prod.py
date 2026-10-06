import os
import dj_database_url
from .settings import *

# ─── Configuración de producción ────────────────────────────────

DEBUG = False

ALLOWED_HOSTS = ['centro-medico-integral.onrender.com', 'localhost', '127.0.0.1']

# ─── Seguridad HTTPS / Proxy ─────────────────────────────────────
# Render usa un proxy inverso con HTTPS
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = True

# HSTS (HTTP Strict Transport Security)
SECURE_HSTS_SECONDS = 31536000  # 1 año
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Cookies seguras
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = 'Lax'

# Headers de seguridad
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'

# CSRF - Confiar en el dominio de Render
CSRF_TRUSTED_ORIGINS = ['https://centro-medico-integral.onrender.com']

# ─── Validación de contraseñas más estricta ─────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 12}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ─── Ruta del admin configurable ────────────────────────────────
ADMIN_URL = os.environ.get('ADMIN_URL', 'admin/')

# ─── Base de datos (Render configura DATABASE_URL automáticamente) ─
DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL'),
        conn_max_age=600,
        ssl_require=True
    )
}

# ─── Static files ────────────────────────────────────────────────
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATIC_URL = '/static/'

# ─── Media files (NO se sirven por nginx, solo por vistas autenticadas) ─
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ─── WhiteNoise (solo archivos estáticos, NO media) ──────────────
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}
WHITENOISE_AUTOREFRESH = False
WHITENOISE_MAX_AGE = 31536000  # 1 año para archivos estáticos

import os
import dj_database_url
from .settings import *

# ─── Configuración de producción ────────────────────────────────

DEBUG = False

ALLOWED_HOSTS = ['centro-medico-integral.onrender.com', 'localhost', '127.0.0.1']

# Seguridad
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = False  # Render maneja HTTPS a nivel de Nginx
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# CSRF - Confiar en el dominio de Render
CSRF_TRUSTED_ORIGINS = ['https://centro-medico-integral.onrender.com']

# Base de datos (Render configura DATABASE_URL automáticamente)
DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL'),
        conn_max_age=600,
        ssl_require=True
    )
}

# Static files
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATIC_URL = '/static/'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

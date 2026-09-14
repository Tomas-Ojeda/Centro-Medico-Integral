import os
from django.core.wsgi import get_wsgi_application
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'consultorio_salto.settings')
application = get_wsgi_application()

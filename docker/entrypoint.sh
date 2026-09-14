#!/bin/sh
set -e

echo "==> Esperando base de datos..."
# Esperar a que PostgreSQL esté listo (el healthcheck de Docker ya lo maneja,
# pero agregamos un pequeño delay extra por si acaso)
sleep 2

echo "==> Aplicando migraciones..."
python manage.py migrate --noinput

echo "==> Recolectando archivos estáticos..."
python manage.py collectstatic --noinput --clear

echo "==> Iniciando servidor Gunicorn..."
exec gunicorn consultorio_salto.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -

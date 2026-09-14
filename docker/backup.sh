#!/bin/sh
# Backup automático diario de PostgreSQL
# Se guarda en docker/backups/ con fecha en el nombre
# Los backups de más de 30 días se eliminan automáticamente

FECHA=$(date +%Y-%m-%d_%H-%M)
ARCHIVO="/backups/backup_${FECHA}.sql.gz"

echo "[$(date)] Iniciando backup → $ARCHIVO"

PGPASSWORD=$DB_PASSWORD pg_dump \
    -h $DB_HOST \
    -U $DB_USER \
    -d $DB_NAME \
    --no-password \
    | gzip > "$ARCHIVO"

if [ $? -eq 0 ]; then
    echo "[$(date)] Backup completado: $ARCHIVO"
else
    echo "[$(date)] ERROR en el backup"
    exit 1
fi

# Eliminar backups de más de 30 días
find /backups -name "backup_*.sql.gz" -mtime +30 -delete
echo "[$(date)] Backups antiguos eliminados"

# Agregar tarea cron: backup todos los días a las 2am
echo "0 2 * * * /backup.sh >> /var/log/backup.log 2>&1" | crontab -

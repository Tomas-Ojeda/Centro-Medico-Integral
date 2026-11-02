# 🏥 Consultorios Médicos - Salto de las Rosas — Instalación con Docker

## Requisitos previos
- Docker Desktop instalado y corriendo
- Terminal (PowerShell o CMD en Windows)

---

## PASO 1 — Configurar las variables de entorno

Abrí el archivo `.env` y completá estos valores:

### 1a. Generar la SECRET_KEY
Abrí una terminal y ejecutá:
```
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```
Copiá el resultado y pegalo en `.env` donde dice `DJANGO_SECRET_KEY=`.

### 1b. Poner la IP de la PC del centro
En Windows ejecutá `ipconfig` y buscá la "Dirección IPv4" (algo como `192.168.1.100`).
Pegala en `.env` donde dice `DJANGO_ALLOWED_HOSTS=`:
```
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.100
```

### 1c. Cambiar las contraseñas de la base de datos
En `.env`, cambiá `DB_PASSWORD` por una contraseña segura (sin espacios ni caracteres especiales raros).

### 1d. Poner tu API key de Anthropic
En `.env`, pegá tu key donde dice `ANTHROPIC_API_KEY=`.

---

## PASO 2 — Levantar los contenedores

Abrí una terminal en la carpeta del proyecto (donde está `docker-compose.yml`) y ejecutá:

```
docker compose up -d --build
```

La primera vez tarda varios minutos porque descarga las imágenes y construye el proyecto.
Cuando termine vas a ver algo como:
```
✔ Container centromedico_db     Started
✔ Container centromedico_web    Started
✔ Container centromedico_nginx  Started
✔ Container centromedico_backup Started
```

---

## PASO 3 — Crear el usuario administrador

```
docker compose exec web python manage.py createsuperuser
```

Seguí las instrucciones para crear el usuario y contraseña.

---

## PASO 4 — Abrir el sistema

Desde la PC del centro:
👉 http://localhost

Desde otras PCs en la misma red WiFi:
👉 http://192.168.1.100  (la IP que pusiste en el paso 1b)

---

## Comandos útiles del día a día

### Ver si todo está corriendo:
```
docker compose ps
```

### Ver los logs si algo falla:
```
docker compose logs web
docker compose logs db
```

### Apagar el sistema:
```
docker compose down
```

### Volver a levantarlo:
```
docker compose up -d
```

### Hacer un backup manual ahora:
```
docker compose exec backup sh /backup.sh
```
Los backups se guardan en `docker/backups/` con la fecha en el nombre.

### Actualizar el sistema (cuando haya cambios en el código):
```
docker compose down
docker compose up -d --build
```

---

## Acceso desde casa — Tailscale (gratuito)

Para que los recepcionistas puedan entrar desde sus casas sin exponer la PC a internet:

1. Creá una cuenta en https://tailscale.com (gratis hasta 3 usuarios)
2. Instalá Tailscale en la PC del centro
3. Instalá Tailscale en cada computadora/teléfono de los recepcionistas
4. Todos se conectan a la misma cuenta (o al mismo "tailnet")
5. Tailscale te da una IP privada para la PC del centro (algo como `100.x.x.x`)
6. Agregá esa IP al `.env` en `DJANGO_ALLOWED_HOSTS`
7. Reiniciá con `docker compose up -d --build`
8. Los recepcionistas acceden desde casa a `http://100.x.x.x`

---

## Backups automáticos (instalación local)

Los backups se hacen automáticamente todos los días a las 2am.
Se guardan en la carpeta `docker/backups/` de tu PC.
Los backups de más de 30 días se eliminan solos.

**Recomendación:** copiá la carpeta `docker/backups/` a un pendrive o Google Drive
una vez por semana como respaldo extra.

---

## Producción en Render (servicio Docker)

El entorno real del centro corre en Render con un **Web Service Docker**
(no usa el runtime Python nativo). Esta sección resume lo necesario para
operarlo; la configuración vigente se administra desde el dashboard de Render.

### Servicio y disco persistente

- **Runtime:** Docker, con `Dockerfile` y `docker/entrypoint.sh`.
- **Plan:** Starter / 0.5 CPU / 512 MB RAM, **1 instancia**.
- **Disco persistente:** 1 GB montado en `/var/data/media`.
- **`MEDIA_ROOT`:** `/var/data/media` (ahí viven únicamente los adjuntos de
  historia clínica).
- **Base de datos:** PostgreSQL de Render (0.1 CPU / 256 MB RAM, 1 GB de disco).

No agregues más de una instancia ni otro disco: el servicio está pensado para
una sola instancia con almacenamiento local.

### Variables de entorno requeridas en Render

| Variable | Valor / descripción |
|----------|---------------------|
| `DJANGO_SECRET_KEY` | Clave secreta de Django |
| `DJANGO_SETTINGS_MODULE` | `consultorio_salto.settings_prod` (ya definida en el `Dockerfile`) |
| `DJANGO_DEBUG` | `False` |
| `DJANGO_ALLOWED_HOSTS` | `centro-medico-integral.onrender.com,localhost,127.0.0.1` |
| `DATABASE_URL` | La inyecta Render desde la base PostgreSQL |
| `MEDIA_ROOT` | `/var/data/media` |
| `ANTHROPIC_API_KEY` | Opcional, para importación de planillas con IA |
| `ADMIN_URL` | Opcional, default `admin/` |
| `NOTAS_VISIBLES_PARA_RECEPCION` | Opcional, default `True` |
| `PAGOS_VISIBLES_PARA_PROFESIONAL` | Opcional, default `False` |

### Migraciones y arranque

En **cada arranque** del contenedor, `docker/entrypoint.sh` ejecuta:

```sh
python manage.py migrate --noinput
python manage.py collectstatic --noinput --clear
```

y después inicia Gunicorn con 3 workers. Por eso no hace falta correr
migraciones a mano después de un deploy. Si una migración falla, el contenedor
no arranca: revisá los logs del servicio en Render.

### Rutina de respaldo en producción

1. **Base de datos:** descargá un dump periódico con `pg_dump` desde una
   máquina con acceso a la base, o usá los backups automáticos del plan de
   Render si están disponibles. Guardá el dump fuera de Render.
2. **Adjuntos:** ingresá como **superusuario** a
   `/admin-tools/respaldo-adjuntos/`. Se descarga un `.zip` con todo el
   contenido de `MEDIA_ROOT`. La vista usa un archivo temporal en `/tmp`
   (disco efímero del contenedor) y streaming, así no carga los archivos en
   memoria, y registra cada descarga en Auditoría.
3. Guardá base y adjuntos juntos, con la misma fecha, en un pendrive, disco
   externo o nube privada. El disco de Render es de **1 GB**: controlá el
   espacio antes de generar respaldos grandes.

`render.yaml` queda como **archivo de referencia**. Si alguna vez sincronizás
un Blueprint, compará antes los planes, el disco y las variables con el
dashboard.

---

## Solución de problemas comunes

### "Port 80 is already in use"
Otro programa está usando el puerto 80. Cambiá en `docker-compose.yml`:
```yaml
ports:
  - "8080:80"
```
Y accedé con `http://localhost:8080`

### "Cannot connect to the Docker daemon"
Docker Desktop no está corriendo. Abrilo desde el menú inicio.

### La página carga pero las imágenes/estilos no se ven
Ejecutá:
```
docker compose exec web python manage.py collectstatic --noinput
```

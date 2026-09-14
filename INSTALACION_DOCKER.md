# 🏥 Centro Médico — Instalación con Docker

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

## Backups automáticos

Los backups se hacen automáticamente todos los días a las 2am.
Se guardan en la carpeta `docker/backups/` de tu PC.
Los backups de más de 30 días se eliminan solos.

**Recomendación:** copiá la carpeta `docker/backups/` a un pendrive o Google Drive
una vez por semana como respaldo extra.

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

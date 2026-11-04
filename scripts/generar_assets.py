"""Genera los assets visuales del login a partir del logo del centro.

Uso:
    python scripts/generar_assets.py
    python scripts/generar_assets.py --source static/img/logo-consultorios.jpg

El script:
  1. Recorta únicamente la cruz con el estetoscopio (sin el texto).
  2. Genera el ícono a color con fondo blanco (para el login).
  3. Genera el ícono blanco con transparencia (para fondos oscuros).
  4. Genera favicon, apple-touch-icon e íconos 192/512 del manifest.

No modifica el logo original. Requiere Pillow.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
IMG_DIR = STATIC_DIR / "img"

# Tamaño de referencia del logo original (500x500). El margen de 14 px se
# escala proporcionalmente si la fuente tiene otra resolución.
REFERENCE_SIZE = 500
MARGIN_REFERENCE = 14
# Umbral para considerar que un píxel pertenece al logo (no al fondo).
CONTENT_THRESHOLD = 18
# Alfa por debajo de este valor se descarta para evitar halos.
ALPHA_CUTOFF = 0.05
# Ganancia del canal alfa del ícono blanco.
ALPHA_GAIN = 2.3

SOURCES = (
    IMG_DIR / "logo-consultorios.jpg",
    IMG_DIR / "logo-consultorios.png",
    STATIC_DIR / "Consultorios (23).png",
)

# Foto del consultorio que se usa como fondo difuminado del login.
BACKGROUND_SOURCE = IMG_DIR / "FONDOCONSULTORIOS.jpg"
BACKGROUND_NAME = "fondo-consultorio.jpg"
BACKGROUND_SIZE = (1600, 1200)
BACKGROUND_BLUR = 18


def _load_source(path: Path) -> Image.Image:
    """Abre la fuente y la compone sobre blanco (soporta JPG y PNG)."""
    image = Image.open(path)
    rgba = image.convert("RGBA")
    background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    background.alpha_composite(rgba)
    return background.convert("RGB")


def _content_mask(image: Image.Image) -> Image.Image:
    """Máscara binaria de los píxeles que no son fondo blanco."""
    white = Image.new("RGB", image.size, (255, 255, 255))
    difference = ImageChops.difference(image, white).convert("L")
    return difference.point(lambda value: 255 if value > CONTENT_THRESHOLD else 0)


def _column_runs(mask: Image.Image, limit: int) -> list[tuple[int, int]]:
    """Devuelve los tramos de columnas con contenido, de izquierda a derecha."""
    pixels = mask.load()
    height = mask.height
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for x in range(limit):
        occupied = any(pixels[x, y] for y in range(height))
        if occupied and start is None:
            start = x
        elif not occupied and start is not None:
            runs.append((start, x - 1))
            start = None
    if start is not None:
        runs.append((start, limit - 1))
    return runs


def find_icon_box(image: Image.Image) -> tuple[int, int, int, int]:
    """Encuentra la caja de la cruz con estetoscopio, sin el texto.

    El logo tiene el ícono a la izquierda y el texto a la derecha. Se toma el
    primer bloque de columnas con contenido y se le agrega un margen
    proporcional de 14 px (referencia 500 px), sin invadir el texto.
    """
    mask = _content_mask(image)
    width, height = mask.size
    runs = _column_runs(mask, int(width * 0.5))
    if not runs:
        raise SystemExit("No se encontró contenido en el logo.")

    icon_run = next(
        (run for run in runs if (run[1] - run[0]) >= width * 0.02),
        runs[0],
    )
    start, end = icon_run
    content_box = mask.crop((start, 0, end + 1, height)).getbbox()
    if content_box is None:
        raise SystemExit("No se pudo recortar el ícono del logo.")

    left, top, right, bottom = content_box
    left += start
    right += start

    margin = round(MARGIN_REFERENCE * min(width, height) / REFERENCE_SIZE)
    next_run = next((run for run in runs if run[0] > end), None)
    if next_run is not None:
        margin = min(margin, next_run[0] - right - 2)
    margin = max(0, min(margin, left, top, width - right, height - bottom))

    return (left - margin, top - margin, right + margin, bottom + margin)


def _fit(image: Image.Image, max_width: int, max_height: int) -> Image.Image:
    """Escala proporcionalmente sin agrandar por encima del tamaño pedido."""
    scale = min(max_width / image.width, max_height / image.height)
    size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    if size == image.size:
        return image.copy()
    return image.resize(size, Image.Resampling.LANCZOS)


def _white_icon(color_crop: Image.Image) -> Image.Image:
    """Ícono blanco con alfa derivado de la luminancia, sin halo."""
    enlarged = color_crop.resize(
        (color_crop.width * 3, color_crop.height * 3),
        Image.Resampling.LANCZOS,
    )
    luminance = ImageOps.grayscale(enlarged)
    cutoff = round(ALPHA_CUTOFF * 255)

    def to_alpha(value: int) -> int:
        alpha = round((255 - value) / 255 * ALPHA_GAIN * 255)
        alpha = max(0, min(255, alpha))
        return 0 if alpha < cutoff else alpha

    alpha = luminance.point(to_alpha)
    icon = Image.new("RGBA", enlarged.size, (255, 255, 255, 255))
    icon.putalpha(alpha)
    return icon


def _transparent_icon(color_image: Image.Image) -> Image.Image:
    """Devuelve el ��cono a color sin el fondo blanco.

    El PNG de color estǭ compuesto sobre blanco. Se calcula el alfa a partir
    de la distancia al blanco y se deshace la composici��n para evitar halos
    claros en los bordes.
    """
    rgb = color_image.convert("RGB")
    pixels = rgb.load()
    result = Image.new("RGBA", rgb.size, (0, 0, 0, 0))
    out = result.load()
    width, height = rgb.size
    for y in range(height):
        for x in range(width):
            r, g, b = pixels[x, y]
            alpha = max(255 - r, 255 - g, 255 - b)
            if alpha == 0:
                continue
            alpha = min(255, round(alpha * 1.55))
            if alpha < 8:
                continue
            ratio = alpha / 255
            out[x, y] = (
                max(0, min(255, round((r - (1 - ratio) * 255) / ratio))),
                max(0, min(255, round((g - (1 - ratio) * 255) / ratio))),
                max(0, min(255, round((b - (1 - ratio) * 255) / ratio))),
                alpha,
            )
    return result


def _blurred_photo(source: Path, size: tuple[int, int]) -> Image.Image:
    """Prepara la foto del consultorio: recorte, suavizado y luz pareja."""
    image = Image.open(source)
    image = ImageOps.exif_transpose(image).convert("RGB")
    target_ratio = size[0] / size[1]
    ratio = image.width / image.height
    if ratio > target_ratio:
        new_width = round(image.height * target_ratio)
        offset = (image.width - new_width) // 2
        image = image.crop((offset, 0, offset + new_width, image.height))
    elif ratio < target_ratio:
        new_height = round(image.width / target_ratio)
        offset = (image.height - new_height) // 2
        image = image.crop((0, offset, image.width, offset + new_height))
    image = image.resize(size, Image.Resampling.LANCZOS)
    image = image.filter(ImageFilter.GaussianBlur(BACKGROUND_BLUR))
    image = ImageEnhance.Brightness(image).enhance(1.05)
    image = ImageEnhance.Color(image).enhance(0.9)
    return image


def _rounded_icon(master: Image.Image, size: int) -> Image.Image:
    """Ícono a color sobre un cuadrado blanco redondeado con margen."""
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    radius = round(size * 0.22)
    draw.rounded_rectangle(
        (0, 0, size - 1, size - 1),
        radius=radius,
        fill=(255, 255, 255, 255),
    )
    inner = round(size * 0.72)
    thumbnail = _fit(master, inner, inner).convert("RGBA")
    position = ((size - thumbnail.width) // 2, (size - thumbnail.height) // 2)
    canvas.alpha_composite(thumbnail, position)
    return canvas


def _square_icon(master: Image.Image, size: int) -> Image.Image:
    """Ícono a color sobre un cuadrado blanco opaco (favicon/apple)."""
    canvas = Image.new("RGB", (size, size), (255, 255, 255))
    inner = round(size * 0.82)
    thumbnail = _fit(master, inner, inner).convert("RGB")
    position = ((size - thumbnail.width) // 2, (size - thumbnail.height) // 2)
    canvas.paste(thumbnail, position)
    return canvas


def generate(source: Path, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    image = _load_source(source)
    box = find_icon_box(image)
    crop = image.crop(box)

    # A color: se escala 3x con LANCZOS y se reduce al tamaño final.
    enlarged_color = crop.resize(
        (crop.width * 3, crop.height * 3),
        Image.Resampling.LANCZOS,
    )
    color_master = _fit(enlarged_color, 2048, 512)

    generated: list[Path] = []

    def save(image_to_save: Image.Image, name: str, **kwargs) -> None:
        path = output_dir / name
        image_to_save.save(path, optimize=True, **kwargs)
        generated.append(path)

    save(color_master, "logo-color.png")

    white_master = _white_icon(crop)
    save(_fit(white_master, 2048, 512), "logo-blanco-512.png")
    save(_fit(white_master, 1024, 256), "logo-blanco-256.png")
    save(_transparent_icon(color_master), "logo-color-transparente.png")

    if BACKGROUND_SOURCE.exists():
        photo = _blurred_photo(BACKGROUND_SOURCE, BACKGROUND_SIZE)
        photo.save(
            output_dir / BACKGROUND_NAME,
            quality=82,
            optimize=True,
            progressive=True,
        )
        generated.append(output_dir / BACKGROUND_NAME)

    save(_square_icon(color_master, 32), "favicon-32.png")
    save(_square_icon(color_master, 180), "apple-touch-icon-180.png")
    save(_rounded_icon(color_master, 192), "icon-192.png")
    save(_rounded_icon(color_master, 512), "icon-512.png")

    return generated


def _resolve_source(explicit: str | None) -> Path:
    if explicit:
        path = Path(explicit)
        if not path.is_absolute():
            path = BASE_DIR / path
        if not path.exists():
            raise SystemExit(f"No existe el archivo indicado: {path}")
        return path
    for candidate in SOURCES:
        if candidate.exists():
            return candidate
    raise SystemExit(
        "No se encontró el logo. Colocá el original en "
        "static/img/logo-consultorios.jpg (o .png) y volvé a ejecutar."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", help="Ruta al logo original")
    parser.add_argument("--out", default=str(IMG_DIR), help="Carpeta de salida")
    args = parser.parse_args()

    source = _resolve_source(args.source)
    output_dir = Path(args.out)
    if not output_dir.is_absolute():
        output_dir = BASE_DIR / output_dir

    print(f"Fuente: {source}")
    print(f"Recorte: {find_icon_box(_load_source(source))}")
    for path in generate(source, output_dir):
        with Image.open(path) as generated:
            print(f"  {path.relative_to(BASE_DIR)}  {generated.size[0]}x{generated.size[1]}")


if __name__ == "__main__":
    main()

"""
Importación masiva de pacientes:
  - Foto/imagen de planilla impresa o manuscrita → Claude Vision API
  - Archivo Excel (.xlsx / .xls) → openpyxl (sin API, local)
  - Archivo CSV (.csv)           → csv stdlib (sin API, local)
"""
import json
import base64
import csv
import io
import re
import urllib.request
from datetime import datetime

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.http import JsonResponse
from django.shortcuts import render

from .models import Paciente, ObraSocial

# ── Constantes ────────────────────────────────────────────────
OBRAS_VALIDAS = [c[0] for c in ObraSocial.choices]

OBRAS_MAP = {
    'osde': 'OSDE', 'osep': 'OSEP',
    'swiss': 'Swiss Medical', 'swiss medical': 'Swiss Medical',
    'medicus': 'Medicus', 'galeno': 'Galeno', 'ioma': 'IOMA',
    'particular': 'Particular', 'part': 'Particular', 'privado': 'Particular',
    'ninguna': 'Particular', 'sin obra': 'Particular',
}

CLAUDE_PROMPT = """Sos un asistente especializado en extraer datos de planillas médicas.
Analizá esta imagen y extraé TODOS los pacientes visibles.

Para cada paciente devolvé exactamente estos campos:
- apellido (string)
- nombre (string, solo el nombre sin apellido)
- dni (string, solo dígitos sin puntos ni espacios; si no se ve claramente dejá "")
- fecha_nacimiento (string YYYY-MM-DD; si no está dejá "")
- telefono (string; si no está dejá "")
- email (string; si no está dejá "")
- direccion (string; si no está dejá "")
- obra_social: EXACTAMENTE uno de: OSDE, OSEP, Swiss Medical, Medicus, Galeno, IOMA, Particular, Otro
- numero_socio (string; si no está dejá "")
- confianza (entero 1-10: qué tan seguro estás de los datos extraídos)

Respondé ÚNICAMENTE con JSON válido sin markdown:
{"pacientes": [...]}

Si no hay pacientes o la imagen no es una planilla:
{"pacientes": [], "error": "descripción"}
"""

# ── Helpers ───────────────────────────────────────────────────

def _normalizar_obra(texto):
    t = str(texto).lower().strip()
    for clave, valor in OBRAS_MAP.items():
        if clave in t:
            return valor
    return 'Otro'


def _normalizar_fecha(texto):
    texto = str(texto).strip().replace('/', '-').replace('.', '-')
    for fmt in ('%d-%m-%Y', '%d-%m-%y', '%Y-%m-%d', '%m-%d-%Y'):
        try:
            return datetime.strptime(texto, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    return ''


def _limpiar_dni(texto):
    return re.sub(r'[^0-9]', '', str(texto))


def _fila_a_paciente(fila_dict):
    """Convierte un dict con claves de encabezado en un dict de paciente normalizado."""
    def buscar(posibles):
        for k in posibles:
            for key in fila_dict:
                if k in str(key).lower():
                    val = fila_dict[key]
                    if val is not None and str(val).strip():
                        return str(val).strip()
        return ''

    apellido = buscar(['apellido', 'apell', 'last'])
    nombre   = buscar(['nombre', 'first', 'name']) 
    dni      = _limpiar_dni(buscar(['dni', 'documento', 'doc', 'cedula']))
    fecha    = _normalizar_fecha(buscar(['fecha', 'nacimiento', 'nac', 'birth']))
    tel      = buscar(['tel', 'celular', 'cel', 'phone', 'movil'])
    email    = buscar(['email', 'mail', 'correo'])
    dir_     = buscar(['direcc', 'domicilio', 'address'])
    obra     = _normalizar_obra(buscar(['obra', 'social', 'mutual', 'cobertura', 'prepaga', 'os']))
    socio    = buscar(['socio', 'afiliado', 'numero'])

    return {
        'apellido': apellido,
        'nombre': nombre,
        'dni': dni,
        'fecha_nacimiento': fecha,
        'telefono': tel,
        'email': email,
        'direccion': dir_,
        'obra_social': obra,
        'numero_socio': socio,
        'confianza': 9 if dni else 5,
    }


# ── Vistas ─────────────────────────────────────────────────────

class ImportarPlanillaView(LoginRequiredMixin, View):
    template_name = 'pacientes/importar_planilla.html'

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        """
        Distingue entre:
          - imagen (base64) → Claude API
          - archivo Excel/CSV (base64 + filename) → procesado local
        """
        try:
            body      = json.loads(request.body)
            tipo      = body.get('tipo', 'imagen')   # 'imagen' | 'excel' | 'csv'
            archivo   = body.get('archivo_b64', '')
            filename  = body.get('filename', '')

            if not archivo:
                return JsonResponse({'error': 'No se recibió ningún archivo.'}, status=400)

            archivo_bytes = base64.b64decode(archivo)

            if tipo == 'imagen':
                media_type = body.get('media_type', 'image/jpeg')
                pacientes  = self._procesar_imagen(archivo_bytes, media_type)
            elif tipo == 'excel':
                pacientes = self._procesar_excel(archivo_bytes)
            elif tipo == 'csv':
                pacientes = self._procesar_csv(archivo_bytes)
            else:
                return JsonResponse({'error': f'Tipo de archivo no soportado: {tipo}'}, status=400)

            return JsonResponse({'pacientes': pacientes})

        except Exception as e:
            return JsonResponse({'error': f'Error al procesar: {str(e)}'}, status=500)

    # ── Claude Vision ───────────────────────────────────────────
    def _procesar_imagen(self, imagen_bytes, media_type):
        api_key = getattr(settings, 'ANTHROPIC_API_KEY', '')
        if not api_key or api_key == 'TU_API_KEY_ACA':
            raise ValueError(
                'Falta la API key de Anthropic. '
                'Abrí consultorio_salto/settings.py y poné tu key en ANTHROPIC_API_KEY.'
            )

        imagen_b64 = base64.b64encode(imagen_bytes).decode('utf-8')

        payload = json.dumps({
            'model': 'claude-sonnet-4-20250514',
            'max_tokens': 4000,
            'messages': [{
                'role': 'user',
                'content': [
                    {
                        'type': 'image',
                        'source': {
                            'type': 'base64',
                            'media_type': media_type,
                            'data': imagen_b64,
                        }
                    },
                    {'type': 'text', 'text': CLAUDE_PROMPT}
                ]
            }]
        }).encode('utf-8')

        req = urllib.request.Request(
            'https://api.anthropic.com/v1/messages',
            data=payload,
            headers={
                'Content-Type': 'application/json',
                'x-api-key': api_key,
                'anthropic-version': '2023-06-01',
            },
            method='POST'
        )

        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode('utf-8'))

        texto = data['content'][0]['text'].strip()
        # Limpiar markdown si Claude lo agrega
        if '```' in texto:
            partes = texto.split('```')
            for p in partes:
                p = p.strip()
                if p.startswith('json'):
                    p = p[4:].strip()
                if p.startswith('{'):
                    texto = p
                    break

        resultado = json.loads(texto)
        if resultado.get('error'):
            raise ValueError(resultado['error'])
        return resultado.get('pacientes', [])

    # ── Excel ────────────────────────────────────────────────────
    def _procesar_excel(self, archivo_bytes):
        try:
            import openpyxl
        except ImportError:
            raise ImportError(
                'Falta openpyxl. Ejecutá: pip install openpyxl'
            )

        wb  = openpyxl.load_workbook(io.BytesIO(archivo_bytes), data_only=True)
        ws  = wb.active
        rows = list(ws.iter_rows(values_only=True))

        if not rows:
            raise ValueError('El archivo Excel está vacío.')

        # Primera fila no vacía = encabezados
        header_idx = 0
        for i, row in enumerate(rows):
            if any(cell is not None for cell in row):
                header_idx = i
                break

        headers   = [str(c).strip() if c is not None else f'col_{j}'
                     for j, c in enumerate(rows[header_idx])]
        pacientes = []

        for row in rows[header_idx + 1:]:
            if not any(cell is not None and str(cell).strip() for cell in row):
                continue
            fila_dict = {headers[j]: row[j] for j in range(min(len(headers), len(row)))}
            p = _fila_a_paciente(fila_dict)
            if p['apellido'] or p['nombre'] or p['dni']:
                pacientes.append(p)

        return pacientes

    # ── CSV ──────────────────────────────────────────────────────
    def _procesar_csv(self, archivo_bytes):
        # Detectar encoding
        for enc in ('utf-8-sig', 'utf-8', 'latin-1', 'cp1252'):
            try:
                texto = archivo_bytes.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise ValueError('No se pudo leer el archivo CSV. Guardalo como UTF-8.')

        # Detectar delimitador
        delimitador = ','
        for delim in (',', ';', '\t', '|'):
            if texto.count(delim) > texto.count(',') * 0.5 or delim == ',':
                delimitador = delim
                break

        reader    = csv.DictReader(io.StringIO(texto), delimiter=delimitador)
        pacientes = []

        for row in reader:
            if not any(str(v).strip() for v in row.values()):
                continue
            p = _fila_a_paciente(dict(row))
            if p['apellido'] or p['nombre'] or p['dni']:
                pacientes.append(p)

        return pacientes


# ── Guardar pacientes confirmados ──────────────────────────────

class GuardarPacientesImportadosView(LoginRequiredMixin, View):

    def post(self, request):
        try:
            body            = json.loads(request.body)
            pacientes_lista = body.get('pacientes', [])
            creados         = []
            errores         = []

            for p in pacientes_lista:
                if p.get('_excluido'):
                    continue

                dni = _limpiar_dni(p.get('dni', ''))

                if not dni or not dni.isdigit():
                    errores.append({'dni': dni, 'nombre': p.get('nombre', ''), 'error': 'DNI inválido o vacío'})
                    continue

                if Paciente.objects.filter(dni=dni).exists():
                    errores.append({'dni': dni, 'nombre': p.get('nombre', ''), 'error': 'DNI ya registrado'})
                    continue

                fecha_nac = None
                for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
                    try:
                        fecha_nac = datetime.strptime(p.get('fecha_nacimiento', ''), fmt).date()
                        break
                    except (ValueError, TypeError):
                        continue

                obra = p.get('obra_social', 'Otro')
                if obra not in OBRAS_VALIDAS:
                    obra = 'Otro'

                try:
                    pac = Paciente.objects.create(
                        nombre         = str(p.get('nombre',   '')).strip(),
                        apellido       = str(p.get('apellido', '')).strip(),
                        dni            = dni,
                        fecha_nacimiento = fecha_nac or datetime(2000, 1, 1).date(),
                        telefono       = str(p.get('telefono',    '')).strip(),
                        email          = str(p.get('email',       '')).strip(),
                        direccion      = str(p.get('direccion',   '')).strip(),
                        obra_social    = obra,
                        numero_socio   = str(p.get('numero_socio','') or '').strip() or None,
                    )
                    creados.append({'id': pac.pk, 'nombre': str(pac)})
                except Exception as e:
                    errores.append({'dni': dni, 'nombre': p.get('nombre', ''), 'error': str(e)})

            return JsonResponse({'creados': len(creados), 'errores': errores})

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

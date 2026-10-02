from django import template
from datetime import date

register = template.Library()

MESES_ES = {
    1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
    5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
    9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
}

DIAS_ES = {
    0: 'Lunes', 1: 'Martes', 2: 'Miércoles', 3: 'Jueves',
    4: 'Viernes', 5: 'Sábado', 6: 'Domingo'
}

@register.filter
def formatear_fecha_es(value):
    """Formatea una fecha en español: 'Lunes 12 de Octubre, 2026'"""
    if not value:
        return ''
    if isinstance(value, str):
        return value
    try:
        dia_semana = DIAS_ES[value.weekday()]
        mes = MESES_ES[value.month]
        return f'{dia_semana} {value.day} de {mes}, {value.year}'
    except (AttributeError, KeyError):
        return str(value)

@register.filter
def formatear_fecha_corta_es(value):
    """Formatea una fecha en español corta: '12 de Octubre, 2026'"""
    if not value:
        return ''
    if isinstance(value, str):
        return value
    try:
        mes = MESES_ES[value.month]
        return f'{value.day} de {mes}, {value.year}'
    except (AttributeError, KeyError):
        return str(value)

@register.filter
def formatear_fecha_hora_es(value):
    """Formatea una fecha con hora en español: '12 de Octubre 2026, 14:30'"""
    if not value:
        return ''
    if isinstance(value, str):
        return value
    try:
        mes = MESES_ES[value.month]
        return f'{value.day} de {mes} {value.year}, {value.strftime("%H:%M")}'
    except (AttributeError, KeyError):
        return str(value)

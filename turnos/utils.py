"""Helpers de presentación y consultas de turnos."""

from datetime import datetime, time, timedelta
from decimal import Decimal, InvalidOperation

from django.utils import timezone

from .models import FormaPago


def rango_del_dia(fecha):
    """Inicio y fin (exclusivo) del día en la zona horaria del proyecto.

    Usar rangos permite aprovechar el índice de ``fecha_hora`` en PostgreSQL
    y SQLite, a diferencia de ``fecha_hora__date``.
    """
    tz = timezone.get_current_timezone()
    inicio = timezone.make_aware(datetime.combine(fecha, time.min), tz)
    return inicio, inicio + timedelta(days=1)


def fecha_desde_request(request, parametro='fecha'):
    """Fecha YYYY-MM-DD del request; hoy si falta o es inválida."""
    valor = request.GET.get(parametro)
    if valor:
        try:
            return datetime.strptime(valor, '%Y-%m-%d').date()
        except (TypeError, ValueError):
            pass
    return timezone.localdate()


def formatear_pesos(valor):
    """Devuelve un monto con separador de miles y coma decimal (es-AR)."""
    if valor is None or valor == '':
        return ''
    try:
        monto = Decimal(valor).quantize(Decimal('0.01'))
    except (InvalidOperation, TypeError, ValueError):
        return str(valor)

    if monto == monto.to_integral_value():
        return f'{int(monto):,}'.replace(',', '.')

    return (
        f'{monto:,.2f}'
        .replace(',', '_')
        .replace('.', ',')
        .replace('_', '.')
    )


def texto_pago(forma_pago, monto):
    """Texto corto para mostrar o auditar un pago."""
    etiqueta = dict(FormaPago.choices).get(forma_pago, forma_pago or 'Sin forma de pago')
    if forma_pago == FormaPago.COBERTURA or monto is None:
        return etiqueta
    return f'{etiqueta} ${formatear_pesos(monto)}'

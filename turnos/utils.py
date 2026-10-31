"""Helpers de presentación para el registro interno de pagos."""

from decimal import Decimal, InvalidOperation

from .models import FormaPago


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

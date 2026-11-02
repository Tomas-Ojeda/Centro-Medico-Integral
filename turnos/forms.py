from decimal import Decimal, InvalidOperation

from django import forms
from django.utils import timezone

from historias.models import VALIDADORES_ADJUNTO_HISTORIA

from .models import (
    FormaPago,
    Plazo,
    SolicitudTurno,
    Turno,
    calcular_fecha_sugerida,
)


class MultipleFileInput(forms.FileInput):
    """Input de archivos que permite seleccionar varios a la vez."""

    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """FileField que valida y devuelve una lista de archivos."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault(
            'widget',
            MultipleFileInput(
                attrs={
                    'multiple': True,
                    'accept': 'image/jpeg,image/png,application/pdf',
                }
            ),
        )
        kwargs.setdefault('validators', VALIDADORES_ADJUNTO_HISTORIA)
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        if data in self.empty_values:
            return []
        if not isinstance(data, (list, tuple)):
            data = [data]
        single_clean = super().clean
        return [single_clean(archivo, initial) for archivo in data]


class TurnoForm(forms.ModelForm):
    adjuntos = MultipleFileField(
        required=False,
        label='Adjuntos de historia clínica',
        help_text='Fotos JPG/PNG o PDF de hasta 10 MB cada uno.',
    )

    class Meta:
        model = Turno
        fields = ['paciente', 'profesional', 'fecha_hora', 'motivo', 'estado', 'observaciones']
        widgets = {
            'fecha_hora': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M'
            ),
            'motivo': forms.Textarea(attrs={'rows': 3}),
            'observaciones': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['fecha_hora'].input_formats = ['%Y-%m-%dT%H:%M']

    def clean_fecha_hora(self):
        fecha_hora = self.cleaned_data.get('fecha_hora')
        if fecha_hora:
            # Sin restricciones de horario: se puede agendar cualquier día y hora
            pass
        return fecha_hora


class SolicitudTurnoForm(forms.ModelForm):
    """Formulario del profesional para pedir el próximo turno de un paciente."""

    fecha_exacta = forms.DateField(
        required=False,
        label='Fecha exacta',
        widget=forms.DateInput(attrs={'type': 'date'}),
    )

    class Meta:
        model = SolicitudTurno
        fields = ['plazo', 'nota']
        widgets = {
            'nota': forms.Textarea(
                attrs={
                    'rows': 3,
                    'placeholder': 'Ej.: Prefiere turnos por la mañana.',
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['plazo'].required = True
        if (
            not self.is_bound
            and self.instance
            and self.instance.pk
            and self.instance.plazo == Plazo.FECHA_EXACTA
        ):
            self.initial['fecha_exacta'] = self.instance.fecha_sugerida

    def clean(self):
        data = super().clean()
        plazo = data.get('plazo')
        fecha_exacta = data.get('fecha_exacta')

        if plazo == Plazo.FECHA_EXACTA:
            if not fecha_exacta:
                self.add_error(
                    'fecha_exacta',
                    'Elegí la fecha exacta del turno.',
                )
            elif fecha_exacta < timezone.localdate():
                self.add_error(
                    'fecha_exacta',
                    'La fecha exacta no puede ser anterior a hoy.',
                )

        return data

    def save(self, commit=True):
        solicitud = super().save(commit=False)
        solicitud.fecha_sugerida = calcular_fecha_sugerida(
            solicitud.plazo,
            self.cleaned_data.get('fecha_exacta'),
        )
        if commit:
            solicitud.save()
        return solicitud


class DescartarSolicitudForm(forms.Form):
    """Motivo opcional al descartar una solicitud de turno."""

    motivo = forms.CharField(
        required=False,
        label='Motivo (opcional)',
        max_length=500,
        widget=forms.Textarea(
            attrs={
                'rows': 2,
                'placeholder': 'Ej.: El paciente pidió otro profesional.',
            }
        ),
    )


class PagoTurnoForm(forms.ModelForm):
    """Registro interno de cobro de un turno (no es comprobante fiscal)."""

    monto = forms.CharField(
        required=False,
        label='Monto',
        help_text='Obligatorio salvo para obra social / sin cargo.',
        widget=forms.TextInput(
            attrs={
                'inputmode': 'decimal',
                'autocomplete': 'off',
                'placeholder': 'Ej: 12000 o 12000,50',
            }
        ),
    )

    class Meta:
        model = Turno
        fields = ['forma_pago', 'monto']
        widgets = {
            'forma_pago': forms.Select(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['forma_pago'].required = False
        if (
            not self.is_bound
            and self.instance
            and self.instance.monto is not None
        ):
            self.initial['monto'] = f'{self.instance.monto:.2f}'

    def clean_monto(self):
        raw = (self.cleaned_data.get('monto') or '').strip()
        if not raw:
            return None

        raw = raw.replace('$', '').replace(' ', '')
        if ',' in raw:
            # Formato argentino: 12.000,50
            raw = raw.replace('.', '').replace(',', '.')

        try:
            monto = Decimal(raw)
        except (InvalidOperation, ValueError):
            raise forms.ValidationError('Ingresá un monto válido.')

        if monto < 0:
            raise forms.ValidationError('El monto no puede ser negativo.')
        if monto >= Decimal('100000000'):
            raise forms.ValidationError('El monto ingresado es demasiado grande.')
        if monto != monto.quantize(Decimal('0.01')):
            raise forms.ValidationError('El monto admite como máximo dos decimales.')

        return monto.quantize(Decimal('0.01'))

    def clean(self):
        data = super().clean()
        forma_pago = data.get('forma_pago')
        monto = data.get('monto')

        if not forma_pago:
            self.add_error(
                'forma_pago',
                'Seleccioná la forma de pago.',
            )
            return data

        if forma_pago == FormaPago.COBERTURA:
            # Obra social / sin cargo: no se cobra monto.
            data['monto'] = None
        elif monto is None:
            self.add_error('monto', 'Ingresá el monto cobrado.')

        return data

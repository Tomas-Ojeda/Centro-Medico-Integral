from django import forms

from historias.models import VALIDADORES_ADJUNTO_HISTORIA

from .models import Turno


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

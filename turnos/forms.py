from django import forms
from django.core.exceptions import ValidationError
from .models import Turno


class TurnoForm(forms.ModelForm):
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

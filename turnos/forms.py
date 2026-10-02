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
            # Verificar que sea lunes a viernes (0=lunes, 6=domingo)
            if fecha_hora.weekday() > 4:  # 5=sábado, 6=domingo
                raise ValidationError('Los turnos solo pueden agendarse de Lunes a Viernes.')
            
            # Verificar horario: 8-12 o 14-18
            hora = fecha_hora.hour
            if not ((8 <= hora < 12) or (14 <= hora < 18)):
                raise ValidationError('Los turnos solo pueden agendarse de 8:00 a 12:00 o de 14:00 a 18:00.')
        
        return fecha_hora

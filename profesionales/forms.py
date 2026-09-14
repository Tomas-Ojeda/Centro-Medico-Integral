from django import forms
from django.core.validators import RegexValidator
from .models import Profesional

dni_validator = RegexValidator(r'^\d+$', 'El DNI solo puede contener números.')

class ProfesionalForm(forms.ModelForm):
    class Meta:
        model = Profesional
        fields = [
            'nombre', 'apellido', 'dni', 'matricula_nacional',
            'matricula_provincial', 'especialidad', 'telefono',
            'email', 'foto', 'fecha_ingreso', 'activo',
        ]
        widgets = {
            'fecha_ingreso': forms.DateInput(attrs={'type': 'date'}),
            'dni': forms.TextInput(attrs={'inputmode': 'numeric', 'pattern': '[0-9]*', 'placeholder': 'Ej: 20456789'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['dni'].validators.append(dni_validator)

    def clean_dni(self):
        dni = self.cleaned_data.get('dni', '')
        if not dni.isdigit():
            raise forms.ValidationError('El DNI solo puede contener números.')
        return dni

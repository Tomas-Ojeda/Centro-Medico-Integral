from django import forms
from django.core.validators import RegexValidator
from .models import Paciente

dni_validator = RegexValidator(r'^\d+$', 'El DNI solo puede contener números.')

class PacienteForm(forms.ModelForm):
    class Meta:
        model = Paciente
        fields = [
            'numero_socio', 'dni', 'nombre', 'apellido',
            'fecha_nacimiento', 'telefono', 'email',
            'direccion', 'obra_social',
        ]
        widgets = {
            'fecha_nacimiento': forms.DateInput(attrs={'type': 'date'}),
            'dni': forms.TextInput(attrs={'placeholder': 'Ej: 30456789', 'inputmode': 'numeric', 'pattern': '[0-9]*'}),
            'telefono': forms.TextInput(attrs={'placeholder': 'Ej: 11-4567-8901'}),
            'email': forms.EmailInput(attrs={'placeholder': 'ejemplo@email.com'}),
            'direccion': forms.TextInput(attrs={'placeholder': 'Av. Corrientes 1234, CABA'}),
            'numero_socio': forms.TextInput(attrs={'placeholder': 'Ej: 1001'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['dni'].validators.append(dni_validator)

    def clean_dni(self):
        dni = self.cleaned_data.get('dni', '')
        if not dni.isdigit():
            raise forms.ValidationError('El DNI solo puede contener números.')
        return dni

from django import forms
from django.core.validators import RegexValidator
from .models import Profesional, Especialidad

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
            'especialidad': forms.TextInput(attrs={'list': 'especialidades-list', 'placeholder': 'Seleccione o escriba una especialidad'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['dni'].validators.append(dni_validator)
        # Hacer que el campo especialidad sea de texto libre
        self.fields['especialidad'] = forms.CharField(
            max_length=50,
            widget=forms.TextInput(attrs={'list': 'especialidades-list', 'placeholder': 'Seleccione o escriba una especialidad'})
        )

    def clean_dni(self):
        dni = self.cleaned_data.get('dni', '')
        if not dni.isdigit():
            raise forms.ValidationError('El DNI solo puede contener números.')
        return dni

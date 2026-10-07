from django import forms
from django.core.validators import RegexValidator
from .models import Profesional, Especialidad

dni_validator = RegexValidator(r'^\d+$', 'El DNI solo puede contener números.')

class ProfesionalForm(forms.ModelForm):
    especialidades = forms.ModelMultipleChoiceField(
        queryset=Especialidad.objects.all(),
        required=False,
        widget=forms.SelectMultiple(attrs={
            'class': 'form-select',
            'size': '5',
        })
    )

    class Meta:
        model = Profesional
        fields = [
            'nombre', 'apellido', 'dni', 'matricula_nacional',
            'matricula_provincial', 'telefono',
            'email', 'foto', 'fecha_ingreso', 'activo',
        ]
        widgets = {
            'fecha_ingreso': forms.DateInput(attrs={'type': 'date'}),
            'dni': forms.TextInput(attrs={'inputmode': 'numeric', 'pattern': '[0-9]*', 'placeholder': 'Ej: 20456789'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['dni'].validators.append(dni_validator)
        # Cargar especialidades existentes del profesional
        if self.instance.pk:
            self.fields['especialidades'].initial = self.instance.especialidades.all()

    def clean_dni(self):
        dni = self.cleaned_data.get('dni', '')
        if not dni.isdigit():
            raise forms.ValidationError('El DNI solo puede contener números.')
        return dni

    def save(self, commit=True):
        instance = super().save(commit=False)
        if commit:
            instance.save()
            self.save_m2m()
        return instance

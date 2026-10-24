from django import forms
from django.core.validators import RegexValidator
from .models import Profesional, Especialidad

dni_validator = RegexValidator(r'^\d+$', 'El DNI solo puede contener números.')

ESPECIALIDADES_COMUNES = [
    'Clínica Médica', 'Cardiología', 'Pediatría', 'Ginecología',
    'Neurología', 'Traumatología', 'Kinesiología', 'Psicología',
    'Odontología', 'Dermatología', 'Oftalmología', 'Psiquiatría',
    'Mastología', 'Urología', 'Gastroenterología', 'Endocrinología',
    'Neumonología', 'Reumatología', 'Infectología', 'Nutrición',
]

class ProfesionalForm(forms.ModelForm):
    especialidades = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'list': 'especialidades-list',
            'placeholder': 'Seleccione o escriba una especialidad',
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
            self.fields['especialidades'].initial = ', '.join([e.nombre for e in self.instance.especialidades.all()])

    def clean_dni(self):
        dni = self.cleaned_data.get('dni', '')
        if not dni.isdigit():
            raise forms.ValidationError('El DNI solo puede contener números.')
        return dni

    def clean_especialidades(self):
        especialidades_str = self.cleaned_data.get('especialidades', '')
        if not especialidades_str:
            return []
        # Separar por coma, normalizar espacios y evitar duplicados por mayúsculas.
        especialidades = []
        vistos = set()
        for parte in especialidades_str.split(','):
            nombre = ' '.join(parte.split())
            if not nombre:
                continue
            clave = nombre.casefold()
            if clave not in vistos:
                vistos.add(clave)
                especialidades.append(nombre)
        return especialidades

    def save(self, commit=True):
        instance = super().save(commit=False)
        if commit:
            instance.save()
            # Guardar especialidades reutilizando las existentes sin distinguir mayúsculas.
            especialidades_nombres = self.cleaned_data.get('especialidades', [])
            if isinstance(especialidades_nombres, str):
                especialidades_nombres = [e.strip() for e in especialidades_nombres.split(',') if e.strip()]
            instance.especialidades.clear()
            for nombre in especialidades_nombres:
                nombre = ' '.join(nombre.split())
                if not nombre:
                    continue
                esp = Especialidad.objects.filter(nombre__iexact=nombre).first()
                if esp is None:
                    esp = Especialidad.objects.create(nombre=nombre)
                instance.especialidades.add(esp)
        return instance

from django import forms
from .models import Consulta, CampoAdicional, ValorCampoAdicional


class ConsultaForm(forms.ModelForm):
    class Meta:
        model = Consulta
        fields = ['profesional', 'fecha_hora', 'motivo', 'diagnostico', 'evolucion', 'tratamiento', 'archivo_adjunto']
        widgets = {
            'fecha_hora': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M'
            ),
            'motivo': forms.Textarea(attrs={'rows': 2}),
            'diagnostico': forms.Textarea(attrs={'rows': 3}),
            'evolucion': forms.Textarea(attrs={'rows': 3}),
            'tratamiento': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['fecha_hora'].input_formats = ['%Y-%m-%dT%H:%M']
        
        # Cargar campos adicionales existentes
        self.campos_adicionales = CampoAdicional.objects.filter(activo=True)
        
        # Si estamos editando, cargar valores existentes
        if self.instance.pk:
            valores_existentes = {
                v.campo_id: v.valor 
                for v in self.instance.campos_adicionales.all()
            }
        else:
            valores_existentes = {}
        
        # Crear campos dinámicos
        for campo in self.campos_adicionales:
            field_name = f'campo_adicional_{campo.pk}'
            if campo.tipo == 'texto':
                self.fields[field_name] = forms.CharField(
                    label=campo.nombre,
                    required=False,
                    widget=forms.TextInput(attrs={'placeholder': f'Ingrese {campo.nombre.lower()}'})
                )
            elif campo.tipo == 'numero':
                self.fields[field_name] = forms.DecimalField(
                    label=campo.nombre,
                    required=False,
                    widget=forms.NumberInput(attrs={'placeholder': f'Ingrese {campo.nombre.lower()}'})
                )
            elif campo.tipo == 'fecha':
                self.fields[field_name] = forms.DateField(
                    label=campo.nombre,
                    required=False,
                    widget=forms.DateInput(attrs={'type': 'date'})
                )
            elif campo.tipo == 'opciones':
                opciones = [(op.strip(), op.strip()) for op in campo.opciones.split(',') if op.strip()]
                self.fields[field_name] = forms.ChoiceField(
                    label=campo.nombre,
                    choices=[('', '---')] + opciones,
                    required=False
                )
            
            # Establecer valor inicial si existe
            if campo.pk in valores_existentes:
                self.fields[field_name].initial = valores_existentes[campo.pk]

    def save(self, commit=True):
        consulta = super().save(commit=commit)
        
        # Guardar valores de campos adicionales
        if commit:
            for campo in self.campos_adicionales:
                field_name = f'campo_adicional_{campo.pk}'
                valor = self.cleaned_data.get(field_name, '')
                
                if valor:
                    ValorCampoAdicional.objects.update_or_create(
                        consulta=consulta,
                        campo=campo,
                        defaults={'valor': str(valor)}
                    )
                else:
                    # Si no hay valor, eliminar si existe
                    ValorCampoAdicional.objects.filter(
                        consulta=consulta,
                        campo=campo
                    ).delete()
        
        return consulta

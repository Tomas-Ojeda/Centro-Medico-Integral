import re
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

    def __init__(self, *args, profesional_fijo=None, **kwargs):
        self.profesional_fijo = profesional_fijo
        super().__init__(*args, **kwargs)
        self.fields['fecha_hora'].input_formats = ['%Y-%m-%dT%H:%M']

        # Para profesionales, el profesional se fuerza al usuario vinculado.
        if profesional_fijo is not None:
            self.fields['profesional'].initial = profesional_fijo
            self.fields['profesional'].disabled = True
            self.fields['profesional'].widget = forms.HiddenInput()

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
        
        # Crear campos dinámicos para campos adicionales existentes
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
        
        # Procesar campos dinámicos del POST (creados con el botón "+")
        self.campos_dinamicos = {}
        if self.data:
            # Buscar todos los campos que empiecen con 'campo_dinamico_'
            pattern = re.compile(r'^campo_dinamico_(\d+)_(\w+)$')
            for key in self.data.keys():
                match = pattern.match(key)
                if match:
                    campo_id = match.group(1)
                    campo_attr = match.group(2)
                    if campo_id not in self.campos_dinamicos:
                        self.campos_dinamicos[campo_id] = {}
                    self.campos_dinamicos[campo_id][campo_attr] = self.data.get(key, '').strip()

    def save(self, commit=True):
        consulta = super().save(commit=commit)
        
        # Guardar valores de campos adicionales existentes
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
            
            # Guardar campos dinámicos (creados con el botón "+")
            for campo_id, datos in self.campos_dinamicos.items():
                nombre = datos.get('nombre', '').strip()
                tipo = datos.get('tipo', 'texto').strip()
                valor = datos.get('valor', '').strip()
                
                # Solo guardar si hay nombre (el valor puede estar vacío para eliminar)
                if nombre:
                    # Crear o obtener el CampoAdicional
                    campo_adicional, created = CampoAdicional.objects.get_or_create(
                        nombre=nombre,
                        defaults={
                            'tipo': tipo if tipo in ['texto', 'numero', 'fecha', 'opciones'] else 'texto',
                            'activo': True
                        }
                    )
                    
                    # Si ya existía pero estaba inactivo, activarlo
                    if not created and not campo_adicional.activo:
                        campo_adicional.activo = True
                        campo_adicional.save()
                    
                    # Guardar o eliminar el valor
                    if valor:
                        ValorCampoAdicional.objects.update_or_create(
                            consulta=consulta,
                            campo=campo_adicional,
                            defaults={'valor': valor}
                        )
                    else:
                        # Si el valor está vacío, eliminar el registro
                        ValorCampoAdicional.objects.filter(
                            consulta=consulta,
                            campo=campo_adicional
                        ).delete()
        
        return consulta

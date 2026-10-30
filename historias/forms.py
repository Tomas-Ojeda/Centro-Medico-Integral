import re

from django import forms
from django.db.models import Q

from profesionales.models import Profesional

from .models import (
    CampoAdicional,
    Consulta,
    NotaClinica,
    ValorCampoAdicional,
)


TIPOS_CAMPO = ['texto', 'numero', 'fecha', 'opciones']


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

        # Campos que se ofrecen en esta consulta: generales + los del
        # profesional que atiende. Los históricos inactivos se muestran
        # aparte para no perder valores ya cargados.
        self.campos_adicionales = self._campos_disponibles()
        self.campos_historicos = self._campos_historicos()

        if self.instance.pk:
            valores_existentes = {
                valor.campo_id: valor.valor
                for valor in self.instance.campos_adicionales.all()
            }
        else:
            valores_existentes = {}

        for campo in list(self.campos_adicionales) + list(self.campos_historicos):
            self._agregar_campo(campo, valores_existentes.get(campo.pk))

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

    def _profesional_consulta(self):
        """Profesional de la consulta que se está creando/editando."""
        if self.profesional_fijo is not None:
            return self.profesional_fijo

        # Al editar como Recepción, manda el profesional enviado en el POST.
        if self.is_bound:
            profesional_id = self.data.get('profesional')
            if profesional_id:
                return Profesional.objects.filter(pk=profesional_id).first()

        if self.instance.pk and self.instance.profesional_id:
            return self.instance.profesional

        inicial = self.initial.get('profesional')
        if inicial:
            if isinstance(inicial, Profesional):
                return inicial
            return Profesional.objects.filter(pk=inicial).first()

        return None

    def _campos_disponibles(self):
        """Campos activos generales o del profesional de la consulta."""
        profesional = self._profesional_consulta()
        filtro = Q(profesional__isnull=True)
        if profesional is not None:
            filtro |= Q(profesional=profesional)
        return list(
            CampoAdicional.objects.filter(activo=True)
            .filter(filtro)
            .select_related('profesional')
        )

    def _campos_historicos(self):
        """Campos con valor en la consulta que ya no se ofrecen."""
        if not self.instance.pk:
            return []
        disponibles = {campo.pk for campo in self.campos_adicionales}
        return [
            valor.campo
            for valor in self.instance.campos_adicionales.select_related('campo')
            if valor.campo_id not in disponibles
        ]

    def _agregar_campo(self, campo, valor_inicial=None):
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
            opciones = [
                (op.strip(), op.strip())
                for op in campo.opciones.split(',')
                if op.strip()
            ]
            self.fields[field_name] = forms.ChoiceField(
                label=campo.nombre,
                choices=[('', '---')] + opciones,
                required=False
            )

        if valor_inicial is not None:
            self.fields[field_name].initial = valor_inicial

    def _obtener_o_crear_campo(self, nombre, tipo):
        """Crea el campo a nombre del profesional logueado (o general)."""
        dueno = self.profesional_fijo
        campo = CampoAdicional.objects.filter(
            nombre=nombre,
            profesional=dueno,
        ).first()

        if campo is None:
            campo = CampoAdicional.objects.create(
                nombre=nombre,
                profesional=dueno,
                tipo=tipo if tipo in TIPOS_CAMPO else 'texto',
                activo=True,
            )
        elif not campo.activo:
            campo.activo = True
            campo.save(update_fields=['activo'])

        return campo

    def save(self, commit=True):
        consulta = super().save(commit=commit)

        if commit:
            # Solo se procesan los campos que realmente se enviaron. Así,
            # un campo quitado con "Quitar" no borra sus valores históricos.
            for campo in list(self.campos_adicionales) + list(self.campos_historicos):
                field_name = f'campo_adicional_{campo.pk}'
                if field_name not in self.data:
                    continue

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
                    campo_adicional = self._obtener_o_crear_campo(nombre, tipo)

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


class NotaClinicaForm(forms.ModelForm):
    class Meta:
        model = NotaClinica
        fields = ['texto']
        widgets = {
            'texto': forms.Textarea(attrs={
                'rows': 3,
                'maxlength': 10000,
                'placeholder': 'Escribí una anotación clínica...',
            }),
        }

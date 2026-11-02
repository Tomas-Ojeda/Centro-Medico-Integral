from django import forms
from django.db.models import Q

from profesionales.models import Profesional

from .models import Derivacion


class DerivacionForm(forms.ModelForm):
    """Formulario para derivar un paciente a otro profesional.

    El origen lo fija la vista para los profesionales. El Admin puede
    elegirlo entre los profesionales que atienden al paciente.
    """

    class Meta:
        model = Derivacion
        fields = ['profesional_origen', 'profesional_destino', 'motivo']
        widgets = {
            'motivo': forms.Textarea(
                attrs={
                    'rows': 4,
                    'placeholder': (
                        'Contá el motivo clínico de la derivación. '
                        'Recepción lo verá al agendar el turno.'
                    ),
                }
            ),
        }

    def __init__(
        self,
        *args,
        paciente=None,
        profesional_origen=None,
        permitir_origen=False,
        profesionales_origen=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.paciente = paciente
        self.profesional_origen = profesional_origen

        if paciente is not None:
            self.instance.paciente = paciente

        destinos = Profesional.objects.filter(activo=True)
        if profesional_origen is not None:
            destinos = destinos.exclude(pk=profesional_origen.pk)
        self.fields['profesional_destino'].queryset = destinos
        self.fields['profesional_destino'].required = True
        self.fields['motivo'].required = True

        if permitir_origen:
            self.fields['profesional_origen'].queryset = (
                profesionales_origen
                if profesionales_origen is not None
                else Profesional.objects.filter(activo=True)
            )
            self.fields['profesional_origen'].required = True
        else:
            # El origen no se elige: es el profesional logueado.
            self.fields.pop('profesional_origen')
            self.instance.profesional_origen = profesional_origen

    def clean(self):
        data = super().clean()
        origen = data.get('profesional_origen') or self.instance.profesional_origen
        destino = data.get('profesional_destino')

        if origen and destino and origen.pk == destino.pk:
            self.add_error(
                'profesional_destino',
                'El profesional de destino debe ser distinto del de origen.',
            )

        return data

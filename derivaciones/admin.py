from django.contrib import admin

from .models import Derivacion


@admin.register(Derivacion)
class DerivacionAdmin(admin.ModelAdmin):
    list_display = [
        'paciente', 'profesional_origen', 'profesional_destino', 'estado',
        'creado', 'vista_en',
    ]
    list_filter = ['estado', 'creado', 'profesional_destino']
    list_select_related = [
        'paciente', 'profesional_origen', 'profesional_destino',
    ]
    search_fields = [
        'paciente__apellido', 'paciente__dni',
        'profesional_origen__apellido', 'profesional_destino__apellido',
    ]
    readonly_fields = ['creado', 'vista_en', 'solicitud_turno']
    date_hierarchy = 'creado'

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change and obj.solicitud_turno_id is None:
            obj.crear_solicitud_turno()

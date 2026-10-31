from django.contrib import admin
from .models import Turno

@admin.register(Turno)
class TurnoAdmin(admin.ModelAdmin):
    list_display = [
        'fecha_hora', 'paciente', 'profesional', 'especialidad', 'estado',
        'forma_pago', 'monto', 'fecha_pago',
    ]
    list_filter = ['estado', 'especialidad', 'forma_pago', 'fecha_hora']
    readonly_fields = ['fecha_pago', 'pago_registrado_por']
    search_fields = ['paciente__apellido', 'paciente__dni', 'profesional__apellido']
    date_hierarchy = 'fecha_hora'

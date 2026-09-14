from django.contrib import admin
from .models import Turno

@admin.register(Turno)
class TurnoAdmin(admin.ModelAdmin):
    list_display = ['fecha_hora', 'paciente', 'profesional', 'especialidad', 'estado']
    list_filter = ['estado', 'especialidad', 'fecha_hora']
    search_fields = ['paciente__apellido', 'paciente__dni', 'profesional__apellido']
    date_hierarchy = 'fecha_hora'

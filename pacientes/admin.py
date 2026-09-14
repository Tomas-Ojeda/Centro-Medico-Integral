from django.contrib import admin
from .models import Paciente

@admin.register(Paciente)
class PacienteAdmin(admin.ModelAdmin):
    list_display = ['apellido', 'nombre', 'dni', 'obra_social', 'telefono', 'fecha_alta']
    list_filter = ['obra_social', 'activo']
    search_fields = ['apellido', 'nombre', 'dni', 'numero_socio']

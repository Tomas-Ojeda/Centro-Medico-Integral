from django.contrib import admin
from .models import Consulta

@admin.register(Consulta)
class ConsultaAdmin(admin.ModelAdmin):
    list_display = ['fecha_hora', 'paciente', 'profesional', 'especialidad']
    list_filter = ['especialidad', 'fecha_hora']
    search_fields = ['paciente__apellido', 'paciente__dni', 'diagnostico']
    date_hierarchy = 'fecha_hora'

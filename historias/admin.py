from django.contrib import admin
from .models import AdjuntoHistoria, Consulta

@admin.register(Consulta)
class ConsultaAdmin(admin.ModelAdmin):
    list_display = ['fecha_hora', 'paciente', 'profesional', 'especialidad']
    list_filter = ['especialidad', 'fecha_hora']
    search_fields = ['paciente__apellido', 'paciente__dni', 'diagnostico']
    date_hierarchy = 'fecha_hora'


@admin.register(AdjuntoHistoria)
class AdjuntoHistoriaAdmin(admin.ModelAdmin):
    list_display = ['creado', 'paciente', 'turno', 'descripcion', 'subido_por']
    list_filter = ['creado']
    search_fields = ['paciente__apellido', 'paciente__dni', 'descripcion']
    readonly_fields = ['creado']

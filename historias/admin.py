from django.contrib import admin
from .models import AdjuntoHistoria, CampoAdicional, Consulta, NotaClinica

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


@admin.register(CampoAdicional)
class CampoAdicionalAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'tipo', 'profesional', 'activo', 'creado']
    list_filter = ['activo', 'tipo', 'profesional']
    search_fields = ['nombre']


@admin.register(NotaClinica)
class NotaClinicaAdmin(admin.ModelAdmin):
    list_display = ['creado', 'paciente', 'autor', 'profesional', 'editado_en']
    list_filter = ['creado', 'editado_en']
    search_fields = ['paciente__apellido', 'paciente__dni', 'texto']
    readonly_fields = ['creado']

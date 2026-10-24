from django.contrib import admin
from .models import Profesional, Especialidad

@admin.register(Profesional)
class ProfesionalAdmin(admin.ModelAdmin):
    list_display = ['apellido', 'nombre', 'get_especialidades', 'matricula_nacional', 'usuario', 'activo']
    list_filter = ['especialidades', 'activo']
    search_fields = ['apellido', 'nombre', 'matricula_nacional', 'usuario__username']
    list_select_related = ['usuario']

    def get_especialidades(self, obj):
        return ", ".join([e.nombre for e in obj.especialidades.all()])
    get_especialidades.short_description = 'Especialidades'

@admin.register(Especialidad)
class EspecialidadAdmin(admin.ModelAdmin):
    list_display = ['nombre']
    search_fields = ['nombre']

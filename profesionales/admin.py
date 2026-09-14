from django.contrib import admin
from .models import Profesional

@admin.register(Profesional)
class ProfesionalAdmin(admin.ModelAdmin):
    list_display = ['apellido', 'nombre', 'especialidad', 'matricula_nacional', 'activo']
    list_filter = ['especialidad', 'activo']
    search_fields = ['apellido', 'nombre', 'matricula_nacional']

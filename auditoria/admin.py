from django.contrib import admin
from .models import LogAcceso


@admin.register(LogAcceso)
class LogAccesoAdmin(admin.ModelAdmin):
    """Admin de solo lectura para los logs de auditoría."""

    list_display = ['usuario', 'fecha_hora', 'accion', 'modelo', 'objeto_id', 'ip']
    list_filter = ['accion', 'modelo', 'fecha_hora']
    search_fields = ['usuario__username', 'ip', 'user_agent']
    readonly_fields = [
        'usuario', 'fecha_hora', 'accion', 'modelo',
        'objeto_id', 'ip', 'user_agent'
    ]
    date_hierarchy = 'fecha_hora'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

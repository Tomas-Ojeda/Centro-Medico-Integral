from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import LogAcceso


class LogAccesoListView(LoginRequiredMixin, ListView):
    """Vista para ver el log de auditoría (solo admin)."""
    model = LogAcceso
    template_name = 'auditoria/log_list.html'
    context_object_name = 'logs'
    paginate_by = 50

    def get_queryset(self):
        return LogAcceso.objects.all().select_related('usuario')

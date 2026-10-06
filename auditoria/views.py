from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from .models import LogAcceso


class LogAccesoListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """Vista para ver el log de auditoría (solo superusuarios)."""
    model = LogAcceso
    template_name = 'auditoria/log_list.html'
    context_object_name = 'logs'
    paginate_by = 50

    def test_func(self):
        return self.request.user.is_superuser

    def get_queryset(self):
        return LogAcceso.objects.all().select_related('usuario')

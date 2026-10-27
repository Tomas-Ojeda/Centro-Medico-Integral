from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views import View

from .models import PALETAS_POR_CLAVE, PreferenciaUsuario


class PaletaUsuarioView(LoginRequiredMixin, View):
    """Guarda la paleta elegida por el usuario autenticado."""

    def post(self, request):
        paleta = request.POST.get('paleta')
        if paleta not in PALETAS_POR_CLAVE:
            return JsonResponse(
                {'ok': False, 'error': 'Paleta inválida.'},
                status=400,
            )

        PreferenciaUsuario.objects.update_or_create(
            usuario=request.user,
            defaults={'paleta': paleta},
        )
        return JsonResponse({'ok': True, 'paleta': paleta})

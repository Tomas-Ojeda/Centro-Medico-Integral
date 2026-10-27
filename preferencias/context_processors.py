from .models import PreferenciaUsuario


def paleta_usuario(request):
    """Expone la paleta del usuario sin crear registros al leer."""
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {'paleta_usuario': 'predeterminado'}

    paleta = (
        PreferenciaUsuario.objects
        .filter(usuario=user)
        .values_list('paleta', flat=True)
        .first()
    )
    return {'paleta_usuario': paleta or 'predeterminado'}

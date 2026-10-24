from django.conf import settings


def nombre_centro(request):
    """Expone el nombre visible del centro a todas las plantillas."""
    return {'NOMBRE_CENTRO': settings.NOMBRE_CENTRO}

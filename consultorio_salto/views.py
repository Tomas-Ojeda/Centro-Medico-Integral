from django.shortcuts import render


def error_403(request, exception=None):
    """Página 403 amigable, mostrando el motivo cuando está disponible."""
    mensaje = str(exception) if exception else ''
    return render(request, '403.html', {'mensaje': mensaje}, status=403)

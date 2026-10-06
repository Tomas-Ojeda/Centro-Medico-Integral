from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from ipware import get_client_ip
from .models import LogAcceso


@receiver(user_logged_in)
def registrar_login(sender, request, user, **kwargs):
    """Registra un login exitoso."""
    ip, _ = get_client_ip(request, proxy_count=1)
    user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]

    LogAcceso.objects.create(
        usuario=user,
        accion=LogAcceso.Accion.LOGIN,
        ip=ip,
        user_agent=user_agent
    )


@receiver(user_logged_out)
def registrar_logout(sender, request, user, **kwargs):
    """Registra un logout."""
    ip, _ = get_client_ip(request, proxy_count=1)
    user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]

    LogAcceso.objects.create(
        usuario=user,
        accion=LogAcceso.Accion.LOGOUT,
        ip=ip,
        user_agent=user_agent
    )


@receiver(user_login_failed)
def registrar_login_fallido(sender, credentials, request, **kwargs):
    """Registra un login fallido."""
    ip, _ = get_client_ip(request, proxy_count=1) if request else (None, None)
    user_agent = request.META.get('HTTP_USER_AGENT', '')[:500] if request else ''

    # Intentar obtener el usuario si existe
    from django.contrib.auth.models import User
    username = credentials.get('username', '')
    try:
        usuario = User.objects.get(username=username)
    except User.DoesNotExist:
        usuario = None

    LogAcceso.objects.create(
        usuario=usuario,
        accion=LogAcceso.Accion.LOGIN_FALLIDO,
        ip=ip,
        user_agent=user_agent
    )

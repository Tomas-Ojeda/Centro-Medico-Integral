"""Permisos de las anotaciones clínicas."""

from django.conf import settings

from consultorio_salto.permisos import (
    es_admin,
    es_profesional,
    es_recepcion,
)


def notas_visibles_para_recepcion():
    return getattr(settings, 'NOTAS_VISIBLES_PARA_RECEPCION', True)


def puede_ver_notas(user):
    """Admin y profesionales siempre; Recepción según configuración."""
    if es_admin(user) or es_profesional(user):
        return True
    if es_recepcion(user):
        return notas_visibles_para_recepcion()
    return False


def puede_crear_notas(user):
    """Solo Admin y profesionales que atienden al paciente."""
    return es_admin(user) or es_profesional(user)


def puede_editar_nota(user, nota):
    """El autor o el Admin."""
    if es_admin(user):
        return True
    return bool(user.is_authenticated and nota.autor_id == user.id)


def puede_borrar_nota(user):
    return es_admin(user)

"""Avisa si hay usuarios que solo difieren en mayúsculas/minúsculas."""

from collections import defaultdict

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        'Lista los usuarios cuyos nombres solo difieren en mayúsculas/minúsculas. '
        'No modifica ni elimina ningún usuario.'
    )

    def handle(self, *args, **options):
        UserModel = get_user_model()
        campo = UserModel.USERNAME_FIELD

        agrupados = defaultdict(list)
        for nombre in UserModel._default_manager.values_list(campo, flat=True):
            agrupados[nombre.casefold()].append(nombre)

        conflictos = sorted(
            sorted(nombres)
            for nombres in agrupados.values()
            if len(nombres) > 1
        )

        if not conflictos:
            self.stdout.write(
                self.style.SUCCESS(
                    'OK: no hay usuarios que difieran solo por '
                    'mayúsculas/minúsculas.'
                )
            )
            return

        self.stderr.write(
            self.style.WARNING(
                'Se encontraron usuarios que solo difieren por '
                'mayúsculas/minúsculas:'
            )
        )
        for nombres in conflictos:
            self.stderr.write('  - ' + ', '.join(nombres))

        self.stderr.write(
            'No se modificó ningún usuario. Revisalos antes de activar '
            'el inicio de sesión insensible a mayúsculas.'
        )
        raise CommandError(
            'Hay nombres de usuario ambiguos; corregilos desde /admin.'
        )

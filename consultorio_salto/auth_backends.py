"""Backend de autenticación que no distingue mayúsculas en el usuario."""

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class CaseInsensitiveBackend(ModelBackend):
    """Autentica con ``username`` sin distinguir mayúsculas de minúsculas.

    Django busca el usuario por su nombre exacto. En el consultorio se suele
    escribir el usuario con otra capitalización (por ejemplo ``Peralta`` en
    lugar de ``peralta``), por lo que este backend hace una búsqueda
    ``iexact`` y luego verifica la contraseña con el flujo normal.

    Si existieran dos usuarios que solo difieren en mayúsculas, no se
    autentica a ninguno para evitar elegir una cuenta al azar. El comando
    ``verificar_usernames`` ayuda a detectar ese caso antes de activarlo.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()

        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        if username is None or password is None:
            return None

        try:
            user = UserModel._default_manager.get(
                **{f'{UserModel.USERNAME_FIELD}__iexact': username}
            )
        except UserModel.DoesNotExist:
            # Mismo costo de hashing que un usuario inexistente en ModelBackend.
            UserModel().set_password(password)
            return None
        except UserModel.MultipleObjectsReturned:
            # Hay usuarios que solo difieren en mayúsculas: usamos la
            # coincidencia exacta para no elegir una cuenta al azar.
            try:
                user = UserModel._default_manager.get(
                    **{UserModel.USERNAME_FIELD: username}
                )
            except (UserModel.DoesNotExist, UserModel.MultipleObjectsReturned):
                return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

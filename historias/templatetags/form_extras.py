from django import template

register = template.Library()


@register.filter
def get_field(form, campo_id):
    """Obtiene un campo adicional del formulario por ID de campo."""
    field_name = f'campo_adicional_{campo_id}'
    if field_name in form.fields:
        return form[field_name]
    return ''


@register.filter
def get_item(dictionary, key):
    """Obtiene un valor de un diccionario por clave."""
    if dictionary is None:
        return ''
    return dictionary.get(key, '')

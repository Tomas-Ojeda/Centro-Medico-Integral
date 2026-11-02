from django.urls import path

from . import views

app_name = 'admin_tools'

urlpatterns = [
    path(
        'respaldo-adjuntos/',
        views.RespaldoAdjuntosView.as_view(),
        name='respaldo_adjuntos',
    ),
]

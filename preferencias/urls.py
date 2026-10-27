from django.urls import path

from . import views

app_name = 'preferencias'

urlpatterns = [
    path('paleta/', views.PaletaUsuarioView.as_view(), name='paleta'),
]

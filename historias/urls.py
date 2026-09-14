from django.urls import path
from . import views

app_name = 'historias'

urlpatterns = [
    path('paciente/<int:paciente_pk>/nueva/', views.ConsultaCreateView.as_view(), name='nueva_consulta'),
    path('<int:pk>/editar/', views.ConsultaUpdateView.as_view(), name='editar_consulta'),
    path('<int:pk>/eliminar/', views.ConsultaDeleteView.as_view(), name='eliminar_consulta'),
]

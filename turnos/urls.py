from django.urls import path
from . import views

app_name = 'turnos'

urlpatterns = [
    path('', views.TurnoAgendaView.as_view(), name='agenda'),
    path('nuevo/', views.TurnoCreateView.as_view(), name='crear'),
    path('exportar/', views.ExportarAgendaCSVView.as_view(), name='exportar_csv'),
    path('buscar-pacientes/', views.BuscarPacientesView.as_view(), name='buscar_pacientes'),
    path('buscar-profesionales/', views.BuscarProfesionalesView.as_view(), name='buscar_profesionales'),
    path('<int:pk>/editar/', views.TurnoUpdateView.as_view(), name='editar'),
    path('<int:pk>/pago/', views.RegistrarPagoView.as_view(), name='registrar_pago'),
    path('<int:pk>/eliminar/', views.TurnoDeleteView.as_view(), name='eliminar'),
    path('<int:pk>/estado/<str:estado>/', views.CambiarEstadoTurnoView.as_view(), name='cambiar_estado'),
]

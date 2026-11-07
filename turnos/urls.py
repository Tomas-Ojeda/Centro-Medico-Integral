from django.urls import path
from . import views

app_name = 'turnos'

urlpatterns = [
    path('', views.TurnoAgendaView.as_view(), name='agenda'),
    path('nuevo/', views.TurnoCreateView.as_view(), name='crear'),
    path('por-agendar/', views.TurnosPorAgendarView.as_view(), name='por_agendar'),
    path(
        'solicitudes/paciente/<int:paciente_pk>/nueva/',
        views.SolicitudTurnoCreateView.as_view(),
        name='solicitar_turno',
    ),
    path(
        'solicitudes/<int:pk>/descartar/',
        views.DescartarSolicitudView.as_view(),
        name='descartar_solicitud',
    ),
    path('exportar/', views.ExportarAgendaCSVView.as_view(), name='exportar_csv'),
    path('sala-de-espera/', views.SalaEsperaJSONView.as_view(), name='sala_espera'),
    path('buscar-pacientes/', views.BuscarPacientesView.as_view(), name='buscar_pacientes'),
    path('buscar-profesionales/', views.BuscarProfesionalesView.as_view(), name='buscar_profesionales'),
    path('<int:pk>/editar/', views.TurnoUpdateView.as_view(), name='editar'),
    path('<int:pk>/pago/', views.RegistrarPagoView.as_view(), name='registrar_pago'),
    path('<int:pk>/llegada/', views.MarcarLlegadaView.as_view(), name='llegada'),
    path('<int:pk>/salida/', views.SalidaSalaView.as_view(), name='salida'),
    path('<int:pk>/volvio/', views.VolvioSalaView.as_view(), name='volvio'),
    path('<int:pk>/eliminar/', views.TurnoDeleteView.as_view(), name='eliminar'),
    path('<int:pk>/estado/<str:estado>/', views.CambiarEstadoTurnoView.as_view(), name='cambiar_estado'),
]

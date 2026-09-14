from django.urls import path
from . import views

app_name = 'turnos'

urlpatterns = [
    path('', views.TurnoAgendaView.as_view(), name='agenda'),
    path('nuevo/', views.TurnoCreateView.as_view(), name='crear'),
    path('exportar/', views.ExportarAgendaCSVView.as_view(), name='exportar_csv'),
    path('<int:pk>/editar/', views.TurnoUpdateView.as_view(), name='editar'),
    path('<int:pk>/eliminar/', views.TurnoDeleteView.as_view(), name='eliminar'),
    path('<int:pk>/estado/<str:estado>/', views.CambiarEstadoTurnoView.as_view(), name='cambiar_estado'),
]

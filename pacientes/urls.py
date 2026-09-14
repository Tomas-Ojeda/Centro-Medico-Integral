from django.urls import path
from . import views
from .views_importar import ImportarPlanillaView, GuardarPacientesImportadosView

app_name = 'pacientes'

urlpatterns = [
    path('', views.PacienteListView.as_view(), name='lista'),
    path('nuevo/', views.PacienteCreateView.as_view(), name='crear'),
    path('importar/', ImportarPlanillaView.as_view(), name='importar'),
    path('importar/guardar/', GuardarPacientesImportadosView.as_view(), name='guardar_importados'),
    path('<int:pk>/', views.PacienteDetailView.as_view(), name='detalle'),
    path('<int:pk>/editar/', views.PacienteUpdateView.as_view(), name='editar'),
    path('<int:pk>/eliminar/', views.PacienteDeleteView.as_view(), name='eliminar'),
]

from django.urls import path
from . import views

app_name = 'historias'

urlpatterns = [
    path('paciente/<int:paciente_pk>/nueva/', views.ConsultaCreateView.as_view(), name='nueva_consulta'),
    path('<int:pk>/editar/', views.ConsultaUpdateView.as_view(), name='editar_consulta'),
    path('<int:pk>/eliminar/', views.ConsultaDeleteView.as_view(), name='eliminar_consulta'),
    path(
        'campos/<int:pk>/quitar/',
        views.QuitarCampoAdicionalView.as_view(),
        name='quitar_campo_adicional',
    ),
    path(
        'paciente/<int:paciente_pk>/notas/nueva/',
        views.NotaClinicaCreateView.as_view(),
        name='nueva_nota',
    ),
    path(
        'notas/<int:pk>/editar/',
        views.NotaClinicaUpdateView.as_view(),
        name='editar_nota',
    ),
    path(
        'notas/<int:pk>/eliminar/',
        views.NotaClinicaDeleteView.as_view(),
        name='eliminar_nota',
    ),
    path('<int:consulta_pk>/descargar/', views.DescargarArchivoAdjuntoView.as_view(), name='descargar_adjunto'),
    path(
        'paciente/<int:paciente_pk>/adjuntos/subir/',
        views.SubirAdjuntoHistoriaView.as_view(),
        name='subir_adjunto_historia',
    ),
    path(
        'adjuntos/<int:pk>/descargar/',
        views.DescargarAdjuntoHistoriaView.as_view(),
        name='descargar_adjunto_historia',
    ),
    path(
        'adjuntos/<int:pk>/eliminar/',
        views.EliminarAdjuntoHistoriaView.as_view(),
        name='eliminar_adjunto_historia',
    ),
]

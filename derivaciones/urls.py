from django.urls import path

from . import views

app_name = 'derivaciones'

urlpatterns = [
    path('', views.DerivacionListView.as_view(), name='lista'),
    path(
        'paciente/<int:paciente_pk>/nueva/',
        views.DerivacionCreateView.as_view(),
        name='crear',
    ),
    path(
        'buscar-profesionales/',
        views.BuscarProfesionalesDerivacionView.as_view(),
        name='buscar_profesionales',
    ),
    path('<int:pk>/', views.DerivacionDetailView.as_view(), name='detalle'),
    path(
        '<int:pk>/cancelar/',
        views.DerivacionCancelView.as_view(),
        name='cancelar',
    ),
    path(
        '<int:pk>/eliminar/',
        views.DerivacionDeleteView.as_view(),
        name='eliminar',
    ),
]

from django.urls import path
from . import views

app_name = 'profesionales'

urlpatterns = [
    path('', views.ProfesionalListView.as_view(), name='lista'),
    path('nuevo/', views.ProfesionalCreateView.as_view(), name='crear'),
    path('<int:pk>/editar/', views.ProfesionalUpdateView.as_view(), name='editar'),
    path('<int:pk>/eliminar/', views.ProfesionalDeleteView.as_view(), name='eliminar'),
]

from django.urls import path
from . import views

app_name = 'auditoria'

urlpatterns = [
    path('', views.LogAccesoListView.as_view(), name='lista'),
]

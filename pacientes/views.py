from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.db.models import Q
from django.http import JsonResponse
from .models import Paciente
from .forms import PacienteForm


class PacienteListView(LoginRequiredMixin, ListView):
    model = Paciente
    template_name = 'pacientes/lista.html'
    context_object_name = 'pacientes'
    paginate_by = 20

    def get_queryset(self):
        qs = Paciente.objects.all()
        q = self.request.GET.get('q', '').strip()
        orden = self.request.GET.get('orden', 'apellido')
        if q:
            qs = qs.filter(
                Q(dni__icontains=q) |
                Q(nombre__icontains=q) |
                Q(apellido__icontains=q) |
                Q(numero_socio__icontains=q)
            )
        if orden == 'reciente':
            qs = qs.order_by('-fecha_alta')
        else:
            qs = qs.order_by('apellido', 'nombre')
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '')
        ctx['orden'] = self.request.GET.get('orden', 'apellido')
        ctx['total'] = Paciente.objects.count()
        return ctx


class PacienteDetailView(LoginRequiredMixin, DetailView):
    model = Paciente
    template_name = 'pacientes/detalle.html'
    context_object_name = 'paciente'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['historial'] = self.object.consultas.select_related('profesional').order_by('-fecha_hora')
        ctx['turnos'] = self.object.turnos.select_related('profesional').order_by('-fecha_hora')[:5]
        ctx['pacientes_sidebar'] = Paciente.objects.all()[:20]
        return ctx


class PacienteCreateView(LoginRequiredMixin, CreateView):
    model = Paciente
    form_class = PacienteForm
    template_name = 'pacientes/formulario.html'
    success_url = reverse_lazy('pacientes:lista')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Nuevo Paciente'
        ctx['accion'] = 'Registrar'
        return ctx


class PacienteUpdateView(LoginRequiredMixin, UpdateView):
    model = Paciente
    form_class = PacienteForm
    template_name = 'pacientes/formulario.html'
    success_url = reverse_lazy('pacientes:lista')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = f'Editar Paciente: {self.object}'
        ctx['accion'] = 'Guardar Cambios'
        return ctx


class PacienteDeleteView(LoginRequiredMixin, DeleteView):
    model = Paciente
    template_name = 'pacientes/confirmar_eliminar.html'
    success_url = reverse_lazy('pacientes:lista')

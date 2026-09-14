from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.db.models import Q
from .models import Profesional
from .forms import ProfesionalForm


class ProfesionalListView(LoginRequiredMixin, ListView):
    model = Profesional
    template_name = 'profesionales/lista.html'
    context_object_name = 'profesionales'

    def get_queryset(self):
        qs = Profesional.objects.all()
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(nombre__icontains=q) | Q(apellido__icontains=q) |
                Q(especialidad__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['total'] = Profesional.objects.count()
        ctx['q'] = self.request.GET.get('q', '')
        return ctx


class ProfesionalCreateView(LoginRequiredMixin, CreateView):
    model = Profesional
    form_class = ProfesionalForm
    template_name = 'profesionales/formulario.html'
    success_url = reverse_lazy('profesionales:lista')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Nuevo Profesional'
        return ctx


class ProfesionalUpdateView(LoginRequiredMixin, UpdateView):
    model = Profesional
    form_class = ProfesionalForm
    template_name = 'profesionales/formulario.html'
    success_url = reverse_lazy('profesionales:lista')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = f'Editar: {self.object}'
        return ctx


class ProfesionalDeleteView(LoginRequiredMixin, DeleteView):
    model = Profesional
    template_name = 'profesionales/confirmar_eliminar.html'
    success_url = reverse_lazy('profesionales:lista')

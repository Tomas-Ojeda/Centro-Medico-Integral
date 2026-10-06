from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.db.models import Q
from .models import Profesional, Especialidad
from .forms import ProfesionalForm
from auditoria.mixins import AuditoriaMixin


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


class ProfesionalCreateView(LoginRequiredMixin, AuditoriaMixin, CreateView):
    model = Profesional
    form_class = ProfesionalForm
    template_name = 'profesionales/formulario.html'
    success_url = reverse_lazy('profesionales:lista')
    accion = 'crear'
    modelo = 'Profesional'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Nuevo Profesional'
        ctx['especialidades'] = Especialidad.values
        return ctx

    def form_valid(self, form):
        response = super().form_valid(form)
        self.registrar_acceso(self.request, form.instance)
        return response


class ProfesionalUpdateView(LoginRequiredMixin, AuditoriaMixin, UpdateView):
    model = Profesional
    form_class = ProfesionalForm
    template_name = 'profesionales/formulario.html'
    success_url = reverse_lazy('profesionales:lista')
    accion = 'editar'
    modelo = 'Profesional'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = f'Editar: {self.object}'
        ctx['especialidades'] = Especialidad.values
        return ctx

    def form_valid(self, form):
        response = super().form_valid(form)
        self.registrar_acceso(self.request, form.instance)
        return response


class ProfesionalDeleteView(LoginRequiredMixin, AuditoriaMixin, DeleteView):
    model = Profesional
    template_name = 'profesionales/confirmar_eliminar.html'
    success_url = reverse_lazy('profesionales:lista')
    accion = 'borrar'
    modelo = 'Profesional'

    def delete(self, request, *args, **kwargs):
        objeto = self.get_object()
        response = super().delete(request, *args, **kwargs)
        self.registrar_acceso(request, objeto)
        return response

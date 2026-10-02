from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.views import View
from django.utils import timezone
from .models import Paciente
from .forms import PacienteForm
from historias.models import Consulta, ValorCampoAdicional
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import io


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


class DescargarHistoriaPDFView(LoginRequiredMixin, View):
    """Descarga la historia clínica completa del paciente como PDF."""
    
    def get(self, request, pk):
        paciente = get_object_or_404(Paciente, pk=pk)
        consultas = Consulta.objects.filter(paciente=paciente).select_related('profesional').order_by('-fecha_hora')
        
        # Crear el PDF
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        
        # Estilos con la estética del proyecto
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(
            name='TitleCustom',
            parent=styles['Title'],
            fontSize=20,
            textColor=colors.HexColor('#1a2035'),
            spaceAfter=4,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))
        styles.add(ParagraphStyle(
            name='Subtitle',
            parent=styles['Normal'],
            fontSize=11,
            textColor=colors.HexColor('#64748b'),
            spaceAfter=24,
            alignment=TA_CENTER
        ))
        styles.add(ParagraphStyle(
            name='SectionTitle',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#1a2035'),
            spaceAfter=10,
            spaceBefore=16,
            fontName='Helvetica-Bold',
            borderWidth=0,
            borderPadding=0,
            borderColor=colors.HexColor('#c9a84c'),
            borderRadius=0
        ))
        styles.add(ParagraphStyle(
            name='Label',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#64748b'),
            spaceAfter=2,
            fontName='Helvetica-Bold'
        ))
        styles.add(ParagraphStyle(
            name='Value',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#1e293b'),
            spaceAfter=6,
            fontName='Helvetica'
        ))
        styles.add(ParagraphStyle(
            name='ConsultaTitle',
            parent=styles['Heading3'],
            fontSize=11,
            textColor=colors.HexColor('#1a2035'),
            spaceAfter=6,
            spaceBefore=12,
            fontName='Helvetica-Bold',
            backColor=colors.HexColor('#f8fafc'),
            borderWidth=1,
            borderColor=colors.HexColor('#e2e8f0'),
            borderPadding=6,
            borderRadius=4
        ))
        styles.add(ParagraphStyle(
            name='Footer',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#94a3b8'),
            alignment=TA_CENTER,
            spaceBefore=20
        ))
        
        # Contenido del PDF
        story = []
        
        # Título
        story.append(Paragraph('Centro Medico Integral - Salto de las Rosas', styles['TitleCustom']))
        story.append(Paragraph('Historia Clínica del Paciente', styles['Subtitle']))
        
        # Línea decorativa
        story.append(Spacer(1, 8))
        
        # Datos del paciente
        story.append(Paragraph('Datos del Paciente', styles['SectionTitle']))
        
        datos_paciente = [
            ['Nombre completo:', f'{paciente.apellido}, {paciente.nombre}'],
            ['DNI:', paciente.dni],
            ['Fecha de nacimiento:', paciente.fecha_nacimiento.strftime('%d/%m/%Y') if paciente.fecha_nacimiento else '—'],
            ['Edad:', f'{paciente.edad} años'],
            ['Obra Social:', paciente.obra_social],
            ['Teléfono:', paciente.telefono or '—'],
            ['Email:', paciente.email or '—'],
            ['Dirección:', paciente.direccion or '—'],
            ['Nº de Socio:', paciente.numero_socio or '—'],
        ]
        
        for label, value in datos_paciente:
            story.append(Paragraph(f'<b>{label}</b> {value}', styles['Value']))
        
        # Campos adicionales del paciente (globales, no por consulta)
        from historias.models import CampoAdicional, ValorCampoAdicional
        campos_adicionales_paciente = ValorCampoAdicional.objects.filter(
            consulta__paciente=paciente
        ).select_related('campo', 'consulta').order_by('campo__nombre', '-consulta__fecha_hora')
        
        # Obtener campos adicionales únicos del paciente (el más reciente de cada tipo)
        campos_vistos = set()
        campos_unicos = []
        for campo in campos_adicionales_paciente:
            if campo.campo_id not in campos_vistos:
                campos_vistos.add(campo.campo_id)
                campos_unicos.append(campo)
        
        if campos_unicos:
            story.append(Spacer(1, 8))
            for campo in campos_unicos:
                story.append(Paragraph(
                    f'<b>{campo.campo.nombre}:</b> {campo.valor}',
                    styles['Value']
                ))
        
        story.append(Spacer(1, 16))
        
        # Historial de consultas
        story.append(Paragraph('Historial de Consultas', styles['SectionTitle']))
        
        if not consultas:
            story.append(Paragraph('No hay consultas registradas.', styles['Value']))
        else:
            for consulta in consultas:
                # Encabezado de la consulta
                fecha_str = consulta.fecha_hora.strftime('%d/%m/%Y %H:%M')
                story.append(Paragraph(
                    f'Consulta del {fecha_str} — {consulta.profesional}',
                    styles['ConsultaTitle']
                ))
                
                if consulta.especialidad:
                    story.append(Paragraph(f'<b>Especialidad:</b> {consulta.especialidad}', styles['Value']))
                
                if consulta.motivo:
                    story.append(Paragraph(f'<b>Motivo:</b> {consulta.motivo}', styles['Value']))
                
                story.append(Paragraph(f'<b>Diagnóstico:</b> {consulta.diagnostico}', styles['Value']))
                
                if consulta.evolucion:
                    story.append(Paragraph(f'<b>Evolución:</b> {consulta.evolucion}', styles['Value']))
                
                if consulta.tratamiento:
                    story.append(Paragraph(f'<b>Tratamiento:</b> {consulta.tratamiento}', styles['Value']))
                
                story.append(Spacer(1, 12))
        
        # Pie de página
        story.append(Spacer(1, 24))
        story.append(Paragraph(
            f'Documento generado el {timezone.now().strftime("%d/%m/%Y %H:%M")}',
            styles['Footer']
        ))
        
        # Construir PDF
        doc.build(story)
        
        # Preparar respuesta
        pdf = buffer.getvalue()
        buffer.close()
        
        response = HttpResponse(content_type='application/pdf')
        filename = f'historia_clinica_{paciente.apellido}_{paciente.nombre}.pdf'.replace(' ', '_').lower()
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response.write(pdf)
        
        return response

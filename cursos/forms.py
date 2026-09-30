"""
================================================================================
ARCHIVO: cursos/forms.py
================================================================================
PROPÓSITO:
    Formularios basados en modelos (ModelForm) para la administración y
    creación de Cursos / Bootcamps por parte del Coordinador Académico.
================================================================================
"""

from django import forms
from .models import Curso, Area


class CursoForm(forms.ModelForm):
    """
    Formulario para la creación y edición de Bootcamps por el Coordinador.
    Utiliza widgets estilizados con clases de Bootstrap 5.
    """
    class Meta:
        model = Curso
        fields = [
            'titulo', 'area', 'descripcion',
            'costo_matricula', 'cupos_disponibles',
            'fecha_inicio', 'fecha_termino'
        ]
        widgets = {
            'titulo': forms.TextInput(attrs={
                'class': 'form-control form-control-lg fs-6',
                'placeholder': 'Ej: Bootcamp Full Stack Python & Django Pro'
            }),
            'area': forms.Select(attrs={
                'class': 'form-select form-select-lg fs-6'
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control fs-6',
                'rows': 4,
                'placeholder': 'Describe los contenidos, tecnologías y objetivos del bootcamp...'
            }),
            'costo_matricula': forms.NumberInput(attrs={
                'class': 'form-control fs-6',
                'placeholder': '250000',
                'step': '1000'
            }),
            'cupos_disponibles': forms.NumberInput(attrs={
                'class': 'form-control fs-6',
                'placeholder': '20',
                'min': '1'
            }),
            'fecha_inicio': forms.DateInput(attrs={
                'class': 'form-control fs-6',
                'type': 'date'
            }),
            'fecha_termino': forms.DateInput(attrs={
                'class': 'form-control fs-6',
                'type': 'date'
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        fecha_inicio = cleaned_data.get('fecha_inicio')
        fecha_termino = cleaned_data.get('fecha_termino')

        if fecha_inicio and fecha_termino and fecha_termino < fecha_inicio:
            self.add_error('fecha_termino', 'La fecha de término no puede ser anterior a la fecha de inicio.')

        return cleaned_data

    def save(self, commit=True):
        curso = super().save(commit=False)
        # Sincronizar cupos totales con los cupos iniciales disponibles
        if not curso.cupos_totales or curso.cupos_totales == 0:
            curso.cupos_totales = curso.cupos_disponibles
        if commit:
            curso.save()
        return curso

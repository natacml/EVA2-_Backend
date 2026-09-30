"""
================================================================================
ARCHIVO: cursos/urls.py
================================================================================
PROPÓSITO:
    Define las rutas (endpoints) de la API REST específicas de la aplicación 'cursos'.
    Este archivo es incluido (imported) en config/urls.py bajo el prefijo '/api/'.
    Por lo tanto, la ruta 'registro/' aquí se traduce a '/api/registro/'.

ARQUITECTURA DE ENRUTAMIENTO (RESTful):
    El enrutamiento sigue los estándares REST. Se agrupan los endpoints según
    el recurso que gestionan (Áreas, Cursos, Carro, Órdenes).
================================================================================
"""

from django.urls import path
from .views import (
    RegistroView, AreaListCreateView, AreaDetailView,
    CursoListCreateView, CursoDetailView, CarroMatriculaView,
    CheckoutView, PagarOrdenView, MisOrdenesView, CambiarEstadoOrdenView
)

urlpatterns = [
    # =========================================================================
    # ENDPOINT DE REGISTRO
    # =========================================================================
    # POST /api/registro/
    # Público. Recibe JSON con datos de usuario y lo registra (hasheando password).
    path('registro/', RegistroView.as_view(), name='registro'),
    
    # =========================================================================
    # ENDPOINTS PÚBLICOS / ADMINISTRACIÓN (CRUD)
    # =========================================================================
    # GET  /api/areas/ : Lista todas las áreas (Público, soporta ?nombre=X).
    # POST /api/areas/ : Crea un nueva área (Solo Coordinador).
    path('areas/', AreaListCreateView.as_view(), name='area-list'),
    # GET, PUT, DELETE /api/areas/<id>/ (Coordinador modifica/elimina).
    path('areas/<int:pk>/', AreaDetailView.as_view(), name='area-detail'),
    
    # GET  /api/cursos/ : Lista todos los cursos (Público, soporta ?area=X&costo=Y).
    # POST /api/cursos/ : Crea un nuevo curso (Solo Coordinador).
    path('cursos/', CursoListCreateView.as_view(), name='curso-list'),
    # GET, PUT, DELETE /api/cursos/<id>/ (Coordinador modifica/elimina).
    path('cursos/<int:pk>/', CursoDetailView.as_view(), name='curso-detail'),
    
    # =========================================================================
    # ENDPOINTS DEL ESTUDIANTE: CARRO Y CHECKOUT
    # =========================================================================
    # GET, POST, DELETE /api/carro-matricula/
    # Muestra, agrega o quita ítems del carrito persistente del estudiante.
    path('carro-matricula/', CarroMatriculaView.as_view(), name='carro-matricula'),
    
    # POST /api/checkout/
    # Transforma los ítems del carro en una MatriculaOrden (Estado: PENDIENTE).
    path('checkout/', CheckoutView.as_view(), name='checkout'),
    
    # POST /api/ordenes/<id>/pagar/
    # Confirma el pago de la orden y descuenta ATÓMICAMENTE los cupos (Estado: PAGADO).
    path('ordenes/<int:pk>/pagar/', PagarOrdenView.as_view(), name='orden-pagar'),
    
    # GET /api/mis-ordenes/
    # Historial filtrado exclusivamente para el usuario autenticado.
    path('mis-ordenes/', MisOrdenesView.as_view(), name='mis-ordenes'),
    
    # =========================================================================
    # ENDPOINTS DEL COORDINADOR: GESTIÓN DE ÓRDENES
    # =========================================================================
    # PATCH /api/ordenes/<id>/estado/
    # Permite al coordinador cambiar el estado (ej: CANCELADO) y repone/descuenta
    # los cupos correspondientemente según la regla de inventario.
    path('ordenes/<int:pk>/estado/', CambiarEstadoOrdenView.as_view(), name='orden-cambiar-estado'),
]
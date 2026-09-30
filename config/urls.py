"""
================================================================================
ARCHIVO: config/urls.py (URLs PRINCIPALES DEL PROYECTO)
================================================================================
PROPÓSITO:
    Punto de entrada del sistema de enrutamiento de Django.
    ROOT_URLCONF en settings.py apunta a este archivo ('config.urls').

    Django recorre urlpatterns EN ORDEN, de arriba hacia abajo,
    buscando la PRIMERA ruta que coincida con la URL del request.

ESTRUCTURA DE RUTAS:
    1. /admin/          → Panel de administración de Django
    2. /api/...         → Todas las rutas de la API REST (JSON)
    3. /api/token/      → Autenticación JWT (login/refresh)
    4. /api/docs/       → Swagger UI (documentación interactiva)
    5. /                → Catálogo de cursos (template HTML)
    6. /catalogo/       → Alias del catálogo
    7. /carro/          → Carrito de matrícula (template HTML)
    8. Catch-all        → Template 404 personalizado (REGLA DE ORO)

REGLA DE ORO DEL 404:
    El catch-all re_path(r'^.*$') al FINAL captura cualquier URL no matcheada.
    Renderiza templates/404.html con el footer del alumno.
    DEBE ir AL FINAL — si estuviera primero, capturaría TODAS las URLs.
================================================================================
"""

from django.contrib import admin
from django.urls import path, include, re_path
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.views import LoginView, LogoutView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from cursos.serializers import CustomTokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenRefreshView, TokenObtainPairView

# Importamos las vistas de template desde views.py
from cursos.views import (
    catalogo_view, carro_view, custom_404_view,
    agregar_al_carro_view, eliminar_del_carro_view,
    crear_curso_view, editar_curso_view, eliminar_curso_view
)


# =============================================================================
# VISTA LOGOUT PERSONALIZADA (EVITA ERROR 405 EN DJANGO)
# =============================================================================
# En Django 5.0+, LogoutView requiere POST por defecto. Al permitir GET y POST,
# evitamos el error 405 Method Not Allowed y renderizamos templates/logout.html.
class CustomLogoutView(LogoutView):
    http_method_names = ['get', 'post', 'options']
    template_name = 'logout.html'

    def get(self, request, *args, **kwargs):
        return self.post(request, *args, **kwargs)


# =============================================================================
# VISTA JWT PERSONALIZADA
# =============================================================================
# Sobreescribimos TokenObtainPairView para usar nuestro serializer personalizado
# que inyecta el claim 'rol' en el payload del JWT.
class CustomTokenView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


# =============================================================================
# URLPATTERNS PRINCIPAL
# =============================================================================
# Django recorre esta lista EN ORDEN. El orden es CRÍTICO:
# 1. Primero: Rutas específicas (admin, API, JWT, Swagger, templates)
# 2. Último: Catch-all 404 (captura todo lo que no coincidió arriba)
urlpatterns = [

    # =========================================================================
    # BLOQUE 1: Panel de Administración
    # =========================================================================
    path('admin/', admin.site.urls),

    # =========================================================================
    # BLOQUE 2: API REST (delegada a cursos/urls.py)
    # =========================================================================
    # include() monta todas las rutas de cursos/urls.py bajo el prefijo /api/.
    # Ejemplo: path('carro-matricula/') en cursos/urls.py → /api/carro-matricula/
    path('api/', include('cursos.urls')),

    # =========================================================================
    # BLOQUE 3: Autenticación JWT
    # =========================================================================
    # POST /api/token/ → Obtener access + refresh token (login)
    # Usa CustomTokenView que inyecta 'rol' y 'username' en el JWT.
    path('api/token/', CustomTokenView.as_view(), name='token_obtain_pair'),

    # POST /api/token/refresh/ → Refrescar access token con el refresh token.
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # =========================================================================
    # BLOQUE 4: Documentación Swagger (drf-spectacular)
    # =========================================================================
    # GET /api/schema/ → Esquema OpenAPI 3.0 raw (Protegido para Coordinador/Staff)
    path('api/schema/', staff_member_required(SpectacularAPIView.as_view(), login_url='login'), name='schema'),

    # GET /api/docs/ → Swagger UI interactivo (Protegido para Coordinador/Staff)
    path('api/docs/', staff_member_required(SpectacularSwaggerView.as_view(url_name='schema'), login_url='login'), name='swagger-ui'),

    # =========================================================================
    # BLOQUE 5: Templates HTML (Capa Visual y Autenticación)
    # =========================================================================
    path('', catalogo_view, name='catalogo'),           # Página principal
    path('catalogo/', catalogo_view, name='catalogo-alt'),  # Alias
    path('carro/', carro_view, name='vista-carro'),      # Carrito del estudiante
    path('carro/agregar/<int:curso_id>/', agregar_al_carro_view, name='agregar_al_carro'),
    path('carro/eliminar/<int:item_id>/', eliminar_del_carro_view, name='eliminar_del_carro'),

    # Gestión de Cursos para Coordinador
    path('cursos/nuevo/', crear_curso_view, name='crear_curso'),
    path('cursos/<int:curso_id>/editar/', editar_curso_view, name='editar_curso'),
    path('cursos/<int:pk>/eliminar/', eliminar_curso_view, name='eliminar_curso'),

    # Autenticación con plantillas personalizadas
    path('login/', LoginView.as_view(template_name='login.html', redirect_authenticated_user=True), name='login'),
    path('logout/', CustomLogoutView.as_view(), name='logout'),
]

# =============================================================================
# CATCH-ALL: REGLA DE ORO DEL 404 (DEBE SER LA ÚLTIMA RUTA)
# =============================================================================
# re_path usa regex: r'^.*$' captura CUALQUIER URL no matcheada arriba.
# Renderiza templates/404.html con el footer del alumno (status=404).
#
# ¿POR QUÉ re_path Y NO path?
# path() usa sintaxis simple que NO soporta comodines.
# re_path() usa expresiones regulares:
#   ^ = inicio de cadena, .* = cualquier carácter 0+ veces, $ = fin de cadena
#   → Juntos: "captura absolutamente cualquier string"
#
# ⚠️ SIEMPRE AL FINAL — si estuviera arriba, capturaría TODO.
urlpatterns += [
    re_path(r'^.*$', custom_404_view, name='custom-404'),
]
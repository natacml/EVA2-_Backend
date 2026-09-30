"""
================================================================================
ARCHIVO: cursos/permissions.py
================================================================================
PROPÓSITO:
    Define permisos PERSONALIZADOS para controlar el acceso a los endpoints
    de la API basándose en el ROL del usuario autenticado.

    Django REST Framework (DRF) incluye permisos genéricos como:
    - AllowAny: Cualquier persona puede acceder.
    - IsAuthenticated: Solo usuarios con sesión activa / token válido.
    - IsAdminUser: Solo usuarios con is_staff=True.

    Sin embargo, nuestro sistema necesita permisos basados en el campo 'rol'
    de CustomUser, que NO es un campo estándar de Django. Por eso creamos
    permisos personalizados heredando de BasePermission.

¿CÓMO FUNCIONAN LOS PERMISOS EN DRF?
    1. Cada vista declara permission_classes = [Permiso1, Permiso2, ...]
    2. Antes de ejecutar la vista, DRF llama a has_permission() de CADA permiso.
    3. Si TODOS retornan True, la vista se ejecuta.
    4. Si ALGUNO retorna False, DRF retorna HTTP 403 Forbidden.
    5. Para permisos a nivel de objeto (ej: "solo el dueño puede ver su carro"),
       se usa has_object_permission().

PERMISOS IMPLEMENTADOS:
    1. EsEstudiante  - Solo usuarios con rol='EST'
    2. EsCoordinador - Solo usuarios con rol='COO'

IMPORTANTE PARA LA DEFENSA:
    Estos permisos se COMBINAN con IsAuthenticated en las vistas.
    IsAuthenticated verifica que el token JWT sea válido.
    EsEstudiante/EsCoordinador verifican el ROL del usuario autenticado.
    Ambos deben ser True para que el acceso sea permitido.
================================================================================
"""

from rest_framework.permissions import BasePermission


# =============================================================================
# PERMISO 1: EsEstudiante
# =============================================================================
class EsEstudiante(BasePermission):
    """
    Permiso personalizado que solo permite el acceso a usuarios con rol 'EST'.

    USO EN VISTAS:
        permission_classes = [IsAuthenticated, EsEstudiante]

    FLUJO DE VERIFICACIÓN:
        1. IsAuthenticated verifica que el request tenga un token JWT válido.
           Si no lo tiene → HTTP 401 Unauthorized.
        2. EsEstudiante verifica que el usuario autenticado tenga rol='EST'.
           Si no lo tiene → HTTP 403 Forbidden con el mensaje definido.

    ATRIBUTO 'message':
        Es el mensaje de error que DRF incluye en la respuesta HTTP 403.
        Si no se define, DRF usa un mensaje genérico en inglés.
    """

    # Mensaje personalizado que se envía en la respuesta HTTP 403
    message = 'Acceso denegado. Solo los estudiantes pueden realizar esta acción.'

    def has_permission(self, request, view):
        """
        Método principal de verificación de permisos.

        Parámetros:
        - request: El objeto HttpRequest de Django, enriquecido por DRF.
                   request.user contiene la instancia de CustomUser autenticada.
        - view: La instancia de la vista que se está intentando acceder.

        Retorna:
        - True: Si el usuario está autenticado Y tiene rol 'EST'.
        - False: En cualquier otro caso (DRF retorna HTTP 403).

        DETALLE TÉCNICO:
        request.user.is_authenticated verifica que no sea AnonymousUser.
        Esto es una doble verificación por seguridad, ya que IsAuthenticated
        normalmente se ejecuta antes. Pero si alguien usa EsEstudiante
        sin IsAuthenticated, esta verificación previene un error.
        """
        return (
            request.user
            and request.user.is_authenticated
            and request.user.rol == 'EST'
        )


# =============================================================================
# PERMISO 2: EsCoordinador
# =============================================================================
class EsCoordinador(BasePermission):
    """
    Permiso personalizado que solo permite el acceso a usuarios con rol 'COO'.

    USO EN VISTAS:
        permission_classes = [IsAuthenticated, EsCoordinador]

    ENDPOINTS QUE USAN ESTE PERMISO:
        - POST/PUT/DELETE /api/cursos/      → CRUD de cursos (solo coordinadores)
        - PATCH /api/matriculas/{id}/estado/ → Cambiar estado de matrícula

    EJEMPLO DE RESPUESTA CUANDO SE DENIEGA (HTTP 403):
    {
        "detail": "Acceso denegado. Solo los coordinadores pueden realizar esta acción."
    }
    """

    message = 'Acceso denegado. Solo los coordinadores pueden realizar esta acción.'

    def has_permission(self, request, view):
        """
        Verifica que el usuario autenticado tenga rol de Coordinador ('COO').

        La lógica es idéntica a EsEstudiante pero verifica rol == 'COO'.
        Se mantiene como clase separada (en vez de parametrizar) para:
        1. Claridad en las vistas: permission_classes = [EsCoordinador]
        2. Mensajes de error específicos por rol.
        3. Facilidad de extensión futura (ej: agregar verificaciones extras
           como horario de trabajo, IP permitida, etc.).
        """
        return (
            request.user
            and request.user.is_authenticated
            and request.user.rol == 'COO'
        )

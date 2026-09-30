"""
================================================================================
ARCHIVO: cursos/views.py
================================================================================
PROPÓSITO:
    Contiene TODAS las vistas (endpoints) de la API REST.
    Cada vista recibe un request HTTP, ejecuta lógica de negocio, y retorna
    una respuesta JSON.

VISTAS IMPLEMENTADAS:
    1. EsCoordinador (Permiso)     → Verifica que el usuario tenga rol 'COO'
    2. RegistroView                → POST /api/registro/
    3. AreaListCreateView          → GET/POST /api/areas/
    4. AreaDetailView              → GET/PUT/DELETE /api/areas/{id}/
    5. CursoListCreateView         → GET/POST /api/cursos/
    6. CursoDetailView             → GET/PUT/DELETE /api/cursos/{id}/
    7. CarroMatriculaView          → GET/POST/DELETE /api/carro-matricula/
    8. CheckoutView                → POST /api/checkout/ (crea orden PENDIENTE)
    9. PagarOrdenView              → POST /api/ordenes/{id}/pagar/ (PENDIENTE→PAGADO)
    10. CambiarEstadoOrdenView     → PATCH /api/ordenes/{id}/estado/ (coordinador)
    11. MisOrdenesView             → GET /api/mis-ordenes/

TRANSACCIONALIDAD (PARA LA DEFENSA):
    Las operaciones críticas usan transaction.atomic() de Django para
    garantizar que si CUALQUIER paso falla, TODOS los cambios se revierten.

    HERRAMIENTAS USADAS:
    - transaction.atomic(): Bloque "todo o nada" en la base de datos.
    - F(): Expresión que ejecuta operaciones directamente en SQL (evita race conditions).
    - select_for_update(): Bloquea filas en PostgreSQL durante la transacción.

REGLA CRÍTICA DE INVENTARIO:
    Los cupos NO se descuentan al agregar al carro.
    SOLO se descuentan al pasar a 'PAGADO'.
    Se REPONEN al pasar a 'CANCELADO' (si estaba PAGADO).
================================================================================
"""

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.db import transaction
from django.db.models import F
from django_filters.rest_framework import DjangoFilterBackend
from .models import Area, Curso, CarroMatricula, CarroItem, MatriculaOrden, OrdenItem, CustomUser
from .serializers import (
    AreaSerializer, CursoSerializer, CarroMatriculaSerializer,
    CarroItemSerializer, MatriculaOrdenSerializer, RegistroSerializer
)


# =============================================================================
# PERMISO PERSONALIZADO: EsCoordinador
# =============================================================================
class EsCoordinador(permissions.BasePermission):
    """
    Permiso personalizado que solo permite acceso a usuarios con rol 'COO'
    o que sean staff de Django (is_staff=True).

    ¿CÓMO FUNCIONA?
    DRF llama a has_permission() ANTES de ejecutar la vista.
    Si retorna True → la vista se ejecuta.
    Si retorna False → DRF retorna HTTP 403 Forbidden.

    Se usa en los endpoints de escritura de cursos y en la gestión de órdenes.
    """
    def has_permission(self, request, view):
        # request.user.is_authenticated verifica que el token JWT sea válido
        # request.user.rol == 'COO' verifica que sea coordinador
        # request.user.is_staff permite que superusuarios también tengan acceso
        return request.user.is_authenticated and (request.user.rol == 'COO' or request.user.is_staff)


# =============================================================================
# VISTA: RegistroView (Registro de Nuevos Usuarios)
# =============================================================================
class RegistroView(generics.CreateAPIView):
    """
    Endpoint: POST /api/registro/
    Acceso: PÚBLICO (AllowAny) — cualquier persona puede registrarse.

    CreateAPIView solo maneja POST. Internamente:
    1. Recibe JSON → lo valida con RegistroSerializer.
    2. Si es válido → llama a serializer.save() (que ejecuta create()).
    3. create() hashea el password con set_password() y crea el carro.
    4. Retorna HTTP 201 con los datos del usuario (sin password).
    """
    queryset = CustomUser.objects.all()
    serializer_class = RegistroSerializer
    permission_classes = [permissions.AllowAny]


# =============================================================================
# VISTAS DE ÁREAS (Público GET, Coordinador POST/PUT/DELETE)
# =============================================================================
class AreaListCreateView(generics.ListCreateAPIView):
    """
    Endpoint: GET/POST /api/areas/
    - GET: PÚBLICO con filtrado por nombre (django-filter).
    - POST: Solo COORDINADORES.

    get_permissions() retorna permisos DIFERENTES según el método HTTP:
    - GET → AllowAny (cualquier persona puede ver las áreas)
    - POST → EsCoordinador (solo coordinadores pueden crear áreas)
    """
    queryset = Area.objects.all()
    serializer_class = AreaSerializer
    filter_backends = [DjangoFilterBackend]
    # filterset_fields habilita filtrado vía query params: /api/areas/?nombre=Desarrollo
    filterset_fields = ['nombre']

    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.AllowAny()]
        return [EsCoordinador()]


class AreaDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Endpoint: GET/PUT/DELETE /api/areas/{id}/
    Misma lógica de permisos que AreaListCreateView.
    """
    queryset = Area.objects.all()
    serializer_class = AreaSerializer

    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.AllowAny()]
        return [EsCoordinador()]


# =============================================================================
# VISTAS DE CURSOS (Público GET con filtros, Coordinador POST/PUT/DELETE)
# =============================================================================
class CursoListCreateView(generics.ListCreateAPIView):
    """
    Endpoint: GET/POST /api/cursos/
    - GET: PÚBLICO con filtrado por 'area' y 'costo_matricula'.
      Ejemplo: GET /api/cursos/?area=1 → solo cursos del área con ID 1.
    - POST: Solo COORDINADORES.

    El filtrado funciona gracias a DjangoFilterBackend configurado en
    settings.py y a filterset_fields que define los campos filtrables.
    """
    queryset = Curso.objects.all()
    serializer_class = CursoSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['area', 'costo_matricula']

    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.AllowAny()]
        return [EsCoordinador()]


class CursoDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Endpoint: GET/PUT/DELETE /api/cursos/{id}/
    Misma lógica de permisos que CursoListCreateView.
    """
    queryset = Curso.objects.all()
    serializer_class = CursoSerializer

    def get_permissions(self):
        if self.request.method == 'GET':
            return [permissions.AllowAny()]
        return [EsCoordinador()]


# =============================================================================
# VISTA: CarroMatriculaView (Carrito de Matrícula Persistente)
# =============================================================================
class CarroMatriculaView(generics.GenericAPIView):
    """
    Endpoint: /api/carro-matricula/
    Acceso: Solo usuarios autenticados (IsAuthenticated).

    Maneja 3 operaciones HTTP sobre el carrito del usuario:
    - GET: Ver el carrito con todos sus ítems.
    - POST: Agregar un curso al carrito (sin descontar cupos).
    - DELETE: Quitar un curso del carrito.

    PERSISTENCIA POST-LOGOUT:
    El carrito se almacena en la BD (tabla CarroMatricula), NO en la sesión.
    Si el usuario cierra sesión y vuelve a entrar, su carrito sigue intacto.

    REGLA DE INVENTARIO:
    Agregar al carro NO descuenta cupos_disponibles.
    Los cupos solo se descuentan al confirmar el pago (PagarOrdenView).
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CarroMatriculaSerializer

    def get(self, request):
        """
        GET /api/carro-matricula/
        Retorna el carrito del usuario con todos sus ítems.

        get_or_create() busca el carrito del usuario; si no existe, lo crea.
        Es atómico en PostgreSQL (evita race conditions si llegan 2 requests).
        """
        carro, _ = CarroMatricula.objects.get_or_create(usuario=request.user)
        serializer = self.get_serializer(carro)
        return Response(serializer.data)

    def post(self, request):
        """
        POST /api/carro-matricula/
        Agrega un curso al carrito. Body: { "curso_id": 5 }

        VALIDACIONES:
        1. El curso debe existir en la BD.
        2. El curso no debe estar ya en el carrito (unique_together lo previene).

        IMPORTANTE: NO se descuentan cupos aquí. Solo se crea el CarroItem.
        """
        carro, _ = CarroMatricula.objects.get_or_create(usuario=request.user)
        curso_id = request.data.get('curso_id')

        # Verificar que el curso exista
        try:
            curso = Curso.objects.get(pk=curso_id)
        except Curso.DoesNotExist:
            return Response({"error": "El curso no existe."}, status=status.HTTP_404_NOT_FOUND)

        # Verificar que no esté duplicado en el carrito
        if CarroItem.objects.filter(carro=carro, curso=curso).exists():
            return Response(
                {"error": "El curso ya está agregado en tu carro activo."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Solo se agrega al carro. Los cupos NO se descuentan aquí.
        CarroItem.objects.create(carro=carro, curso=curso)
        serializer = self.get_serializer(carro)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def delete(self, request):
        """
        DELETE /api/carro-matricula/
        Elimina un curso del carrito. Body: { "curso_id": 5 }
        """
        carro, _ = CarroMatricula.objects.get_or_create(usuario=request.user)
        curso_id = request.data.get('curso_id')
        try:
            item = CarroItem.objects.get(carro=carro, curso_id=curso_id)
            item.delete()
            serializer = self.get_serializer(carro)
            return Response(serializer.data)
        except CarroItem.DoesNotExist:
            return Response({"error": "El ítem no está en el carro."}, status=status.HTTP_404_NOT_FOUND)


# =============================================================================
# VISTA: CheckoutView (Crear Orden desde el Carro - Estado PENDIENTE)
# =============================================================================
class CheckoutView(generics.GenericAPIView):
    """
    Endpoint: POST /api/checkout/
    Acceso: Solo usuarios autenticados.

    Convierte el contenido del carro en una MatriculaOrden con estado 'PENDIENTE'.

    REGLA CRÍTICA:
    El checkout NO descuenta cupos. Solo:
    1. Crea la orden en estado PENDIENTE.
    2. Copia los cursos del carro como OrdenItems con precio congelado.
    3. Vacía el carro.

    Los cupos se descuentan SOLO cuando se paga (PagarOrdenView).

    ¿POR QUÉ SEPARAR CHECKOUT Y PAGO?
    Para simular un flujo realista de e-commerce:
    - Checkout = crear la orden (como un resumen antes de pagar).
    - Pago = confirmar y ejecutar el descuento de inventario.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = MatriculaOrdenSerializer

    def post(self, request):
        """
        POST /api/checkout/
        NO recibe body — trabaja directamente con el carro del usuario.
        """

        # =====================================================================
        # PASO 1: Obtener el carro y verificar que no esté vacío
        # =====================================================================
        try:
            carro = CarroMatricula.objects.get(usuario=request.user)
        except CarroMatricula.DoesNotExist:
            return Response(
                {"error": "No tienes un carro activo."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # select_related('curso') hace un JOIN para traer los datos del curso
        # en UNA sola query SQL (optimización "eager loading").
        items_carro = carro.items.select_related('curso').all()
        if not items_carro.exists():
            return Response(
                {"error": "El carro está vacío."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # =====================================================================
        # PASO 2: TRANSACCIÓN ATÓMICA - Crear orden y vaciar carro
        # =====================================================================
        # transaction.atomic() garantiza que si algo falla dentro del bloque,
        # TODOS los cambios se revierten (rollback).
        with transaction.atomic():
            # Crear la orden en estado PENDIENTE (SIN descontar cupos)
            orden = MatriculaOrden.objects.create(
                usuario=request.user,
                estado='PENDIENTE'
            )

            # Copiar cada ítem del carro como OrdenItem con precio congelado
            for item in items_carro:
                OrdenItem.objects.create(
                    orden=orden,
                    curso=item.curso,
                    # precio_al_matricular: Snapshot del precio ACTUAL del curso.
                    # Si el precio cambia después, este registro preserva
                    # lo que el estudiante debía pagar al momento del checkout.
                    precio_al_matricular=item.curso.costo_matricula
                )

            # Vaciar el carro después de generar la orden
            items_carro.delete()

        serializer = self.get_serializer(orden)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# =============================================================================
# VISTA: PagarOrdenView (PENDIENTE → PAGADO - Descuento Atómico de Cupos)
# =============================================================================
class PagarOrdenView(generics.GenericAPIView):
    """
    Endpoint: POST /api/ordenes/{id}/pagar/
    Acceso: Solo el ESTUDIANTE dueño de la orden (IsAuthenticated + usuario=request.user).

    ESTA ES LA VISTA MÁS CRÍTICA DEL SISTEMA (PARA LA DEFENSA).

    Cambia el estado de PENDIENTE a PAGADO y descuenta los cupos ATÓMICAMENTE.

    TRANSACCIONALIDAD CON transaction.atomic():
    ============================================
    ¿Qué es una transacción atómica?
    Es un bloque de operaciones de BD que se ejecutan como UNA SOLA UNIDAD.
    Si CUALQUIER operación falla → ROLLBACK (todo se revierte).
    Si todas pasan → COMMIT (todo se confirma).

    DESCUENTO CON F() (PARA LA DEFENSA):
    ======================================
    F('cupos_disponibles') - 1 se traduce a SQL directo:
        UPDATE cursos_curso SET cupos_disponibles = cupos_disponibles - 1 WHERE id = X;

    ¿Por qué F() y no curso.cupos_disponibles -= 1?
    SIN F() (PELIGROSO - Race Condition):
        Proceso A lee cupos=10, Proceso B lee cupos=10
        Proceso A escribe cupos=9, Proceso B escribe cupos=9
        Resultado: Solo se descontó 1, debían ser 2 → INCONSISTENCIA.

    CON F() (SEGURO):
        UPDATE SET cupos = cupos - 1  (ejecutado en SQL por PostgreSQL)
        PostgreSQL serializa las escrituras con bloqueos de fila → CORRECTO.

    select_for_update():
    ====================
    Bloquea las filas seleccionadas para que NADIE MÁS pueda leerlas/modificarlas
    hasta que termine nuestra transacción. Evita lecturas sucias (dirty reads).
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = MatriculaOrdenSerializer

    def post(self, request, pk):
        """
        POST /api/ordenes/{pk}/pagar/
        pk viene de la URL: /api/ordenes/42/pagar/ → pk=42
        """

        # =====================================================================
        # PASO 1: Obtener la orden y validar que pertenezca al usuario
        # =====================================================================
        try:
            # usuario=request.user garantiza que solo el dueño puede pagar su orden
            orden = MatriculaOrden.objects.get(pk=pk, usuario=request.user)
        except MatriculaOrden.DoesNotExist:
            return Response(
                {"error": "Orden no encontrada."},
                status=status.HTTP_404_NOT_FOUND
            )

        # =====================================================================
        # PASO 2: Validar que la orden esté en estado PENDIENTE
        # =====================================================================
        if orden.estado != 'PENDIENTE':
            return Response(
                {"error": f"Solo se pueden pagar órdenes en estado PENDIENTE. Estado actual: {orden.estado}."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # =====================================================================
        # PASO 3: TRANSACCIÓN ATÓMICA - Verificar stock y descontar cupos
        # =====================================================================
        with transaction.atomic():
            # -----------------------------------------------------------------
            # 3.1: Bloquear filas de cursos con select_for_update()
            # -----------------------------------------------------------------
            # Obtenemos los IDs de los cursos de la orden
            cursos_ids = orden.items.values_list('curso_id', flat=True)

            # select_for_update() BLOQUEA las filas en PostgreSQL.
            # Ningún otro proceso puede modificar estos cursos hasta que
            # nuestra transacción termine (commit o rollback).
            cursos = Curso.objects.select_for_update().filter(pk__in=cursos_ids)

            # -----------------------------------------------------------------
            # 3.2: Validar que TODOS los cursos tengan cupos disponibles
            # -----------------------------------------------------------------
            for curso in cursos:
                if curso.cupos_disponibles < 1:
                    # Si algún curso no tiene cupos, retornamos error.
                    # Al salir del bloque atomic, se liberan los bloqueos.
                    return Response(
                        {"error": f"Sin cupos disponibles para '{curso.titulo}'."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # -----------------------------------------------------------------
            # 3.3: Descontar cupos atómicamente con F()
            # -----------------------------------------------------------------
            # F('cupos_disponibles') - 1 genera SQL:
            # UPDATE cursos_curso SET cupos_disponibles = cupos_disponibles - 1
            # La operación se ejecuta DIRECTAMENTE en PostgreSQL,
            # no en Python, evitando race conditions.
            for curso in cursos:
                curso.cupos_disponibles = F('cupos_disponibles') - 1
                curso.save(update_fields=['cupos_disponibles'])

            # -----------------------------------------------------------------
            # 3.4: Cambiar estado de la orden a PAGADO
            # -----------------------------------------------------------------
            orden.estado = 'PAGADO'
            orden.save(update_fields=['estado'])

        # =====================================================================
        # PASO 4: Refrescar y retornar respuesta
        # =====================================================================
        # refresh_from_db() recarga los datos de la BD porque después de usar
        # F(), los valores en la instancia Python quedan como objetos F,
        # no como números reales. El refresh obtiene el valor numérico actual.
        orden.refresh_from_db()
        serializer = self.get_serializer(orden)
        return Response(serializer.data)


# =============================================================================
# VISTA: CambiarEstadoOrdenView (Gestión de Estado por Coordinador)
# =============================================================================
class CambiarEstadoOrdenView(generics.GenericAPIView):
    """
    Endpoint: PATCH /api/ordenes/{id}/estado/
    Acceso: Solo COORDINADORES (EsCoordinador).

    Permite al coordinador cambiar el estado de CUALQUIER orden.

    REGLAS DE TRANSICIÓN Y CUPOS (PARA LA DEFENSA):
    =================================================
    El manejo de cupos depende de las transiciones de estado:

    1. PAGADO → CANCELADO: RESTAURA cupos (+1 por curso)
       Porque los cupos se habían descontado al pagar.

    2. CANCELADO → PAGADO: DESCUENTA cupos (-1 por curso)
       Porque se está reactivando una orden cancelada.

    3. PENDIENTE → CANCELADO: NO toca cupos
       Porque nunca se descontaron (la orden nunca fue pagada).

    4. PENDIENTE → PAGADO: DESCUENTA cupos (-1 por curso)
       Porque es equivalente a un pago.

    LÓGICA GENERALIZADA:
    - Si el nuevo estado es PAGADO y el anterior NO era PAGADO → descontar.
    - Si el estado anterior era PAGADO y el nuevo NO es PAGADO → restaurar.
    - En otros casos → no tocar cupos.
    """
    permission_classes = [EsCoordinador]
    serializer_class = MatriculaOrdenSerializer

    def patch(self, request, pk):
        """
        PATCH /api/ordenes/{pk}/estado/
        Body: { "estado": "CANCELADO" }
        """

        # =====================================================================
        # PASO 1: Obtener la orden
        # =====================================================================
        try:
            orden = MatriculaOrden.objects.get(pk=pk)
        except MatriculaOrden.DoesNotExist:
            return Response(
                {"error": "Orden no encontrada."},
                status=status.HTTP_404_NOT_FOUND
            )

        # =====================================================================
        # PASO 2: Validar el nuevo estado
        # =====================================================================
        nuevo_estado = request.data.get('estado')
        estados_validos = ['PENDIENTE', 'PAGADO', 'CANCELADO']
        if nuevo_estado not in estados_validos:
            return Response(
                {"error": f"Estado inválido. Use: {', '.join(estados_validos)}."},
                status=status.HTTP_400_BAD_REQUEST
            )

        estado_anterior = orden.estado
        if estado_anterior == nuevo_estado:
            return Response(
                {"error": f"La orden ya está en estado {nuevo_estado}."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # =====================================================================
        # PASO 3: TRANSACCIÓN ATÓMICA con lógica de cupos
        # =====================================================================
        with transaction.atomic():
            # Bloquear filas de cursos para evitar race conditions
            cursos_ids = orden.items.values_list('curso_id', flat=True)
            cursos = Curso.objects.select_for_update().filter(pk__in=cursos_ids)

            # -----------------------------------------------------------------
            # CASO A: Transición HACIA PAGADO (descontar cupos)
            # -----------------------------------------------------------------
            # Se entra aquí cuando:
            # - PENDIENTE → PAGADO (pago por coordinador)
            # - CANCELADO → PAGADO (reactivación de orden)
            if nuevo_estado == 'PAGADO' and estado_anterior != 'PAGADO':
                # Primero verificar que haya cupos para TODOS los cursos
                for curso in cursos:
                    if curso.cupos_disponibles < 1:
                        return Response(
                            {"error": f"Sin cupos disponibles para '{curso.titulo}'."},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                # Si todos tienen cupos, descontar atómicamente con F()
                for curso in cursos:
                    curso.cupos_disponibles = F('cupos_disponibles') - 1
                    curso.save(update_fields=['cupos_disponibles'])

            # -----------------------------------------------------------------
            # CASO B: Transición DESDE PAGADO (restaurar cupos)
            # -----------------------------------------------------------------
            # Se entra aquí cuando:
            # - PAGADO → CANCELADO (cancelación → cupos vuelven al curso)
            # - PAGADO → PENDIENTE (revertir pago → cupos vuelven al curso)
            elif estado_anterior == 'PAGADO' and nuevo_estado != 'PAGADO':
                for curso in cursos:
                    # F('cupos_disponibles') + 1: REPONE los cupos
                    # Es la operación INVERSA al descuento.
                    curso.cupos_disponibles = F('cupos_disponibles') + 1
                    curso.save(update_fields=['cupos_disponibles'])

            # CASO C: Transiciones que NO tocan cupos
            # - PENDIENTE → CANCELADO: Nunca se descontaron cupos
            # (No requiere código, simplemente no entra a ningún if)

            # Actualizar el estado de la orden
            orden.estado = nuevo_estado
            orden.save(update_fields=['estado'])

        # Refrescar para obtener valores reales después de F()
        orden.refresh_from_db()
        serializer = self.get_serializer(orden)
        return Response(serializer.data)


# =============================================================================
# VISTA: MisOrdenesView (Historial de Órdenes del Estudiante)
# =============================================================================
class MisOrdenesView(generics.ListAPIView):
    """
    Endpoint: GET /api/mis-ordenes/
    Acceso: Solo usuarios autenticados.

    Retorna SOLO las órdenes del usuario autenticado (filtrado por seguridad).
    Sin el filtro usuario=request.user, cualquier estudiante vería TODAS las órdenes.
    """
    serializer_class = MatriculaOrdenSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # swagger_fake_view evita errores cuando drf-spectacular genera el esquema
        if getattr(self, 'swagger_fake_view', False):
            return MatriculaOrden.objects.none()
        return MatriculaOrden.objects.filter(usuario=self.request.user)


# =============================================================================
# VISTAS DE TEMPLATE HTML (Capa Visual)
# =============================================================================
# NOTA IMPORTANTE:
# El sistema es 100% API REST (JSON). Estas vistas de template son la
# CAPA VISUAL complementaria exigida por la rúbrica. Los datos se cargan
# desde la API con JavaScript (fetch), NO con context de Django.
#
# Son las ÚNICAS vistas que usan render() — todas las demás retornan JSON.
# =============================================================================

from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.contrib import messages


def catalogo_view(request):
    """
    Vista de template: Renderiza la página del catálogo de cursos.
    URL: / (raíz del sitio) y /catalogo/
    PÚBLICA: Accesible por cualquier usuario (anónimo, estudiante o coordinador).
    """
    cursos = Curso.objects.select_related('area').all()
    return render(request, 'catalogo.html', {'cursos': cursos})


def carro_view(request):
    """
    Vista de template: Renderiza la página del carrito de matrícula.
    URL: /carro/

    REGLAS ESTRICTAS DE ACCESO:
    - Coordinador (is_staff): NO debe tener acceso ni ver el carro (administra, no compra).
      Se redirige al catálogo.
    - Visitante no autenticado: Se redirige al inicio de sesión.
    - Estudiante (autenticado y no staff): Acceso al carro de compras.
    """
    if not request.user.is_authenticated:
        return redirect('login')

    if request.user.is_staff:
        # El coordinador administra la plataforma y no compra cursos.
        return redirect('catalogo')

    items_carro = []
    total_carro = 0
    try:
        carro, _ = CarroMatricula.objects.get_or_create(usuario=request.user)
        items_carro = carro.items.select_related('curso').all()
        total_carro = sum(item.curso.costo_matricula for item in items_carro)
    except Exception:
        pass

    return render(request, 'carro.html', {'items_carro': items_carro, 'total_carro': total_carro})


@login_required
@require_POST
def agregar_al_carro_view(request, curso_id):
    """
    Vista que recibe la petición POST desde catalogo.html para agregar un curso al carro.
    - @login_required: Requiere que el usuario esté autenticado.
    - @require_POST: Exige método POST con validación automática de CSRF token.
    - get_or_create: Evita ítems duplicados en el carro de compras.
    - Redirige de vuelta al catálogo con mensaje de feedback al usuario.
    """
    if request.user.is_staff:
        messages.warning(request, "Los coordinadores no pueden comprar cursos; su rol es administrar la plataforma.")
        return redirect('catalogo')

    curso = get_object_or_404(Curso, id=curso_id)

    if curso.cupos_disponibles <= 0:
        messages.warning(request, f"Lo sentimos, el curso '{curso.titulo}' no tiene cupos disponibles.")
        return redirect('catalogo')

    carro, _ = CarroMatricula.objects.get_or_create(usuario=request.user)
    item, creado = CarroItem.objects.get_or_create(carro=carro, curso=curso)

    if creado:
        messages.success(request, f"¡'{curso.titulo}' se agregó exitosamente a tu Carro de Compra!")
    else:
        messages.info(request, f"El curso '{curso.titulo}' ya está en tu Carro de Compra.")

    return redirect('catalogo')


@login_required
@require_POST
def eliminar_del_carro_view(request, item_id):
    """
    Elimina un curso específico del carro de matrícula del estudiante autenticado.
    """
    carro = get_object_or_404(CarroMatricula, usuario=request.user)
    item = get_object_or_404(CarroItem, id=item_id, carro=carro)
    titulo = item.curso.titulo
    item.delete()
    messages.success(request, f"'{titulo}' fue eliminado de tu carro.")
    return redirect('vista-carro')


def crear_curso_view(request):
    """
    ===========================================================================
    VISTA FRONTEND: crear_curso_view
    ===========================================================================
    Vista basada en funciones (FBV) para que el Coordinador registre Bootcamps
    directamente desde la interfaz web, saltándose el panel de /admin/.

    SEGURIDAD Y ROLES:
    - is_authenticated: El usuario debe haber iniciado sesión.
    - is_staff: Funciona como un RBAC (Role-Based Access Control). Si un
      estudiante intenta acceder, se le redirige al catálogo.

    FLUJO DEL FORMULARIO (ModelForm):
    1. GET: Retorna `CursoForm()` vacío para renderizar el HTML.
    2. POST: Carga `request.POST` en el form. Si `is_valid()` es True, ejecuta
       `form.save()` que hace el INSERT en PostgreSQL.
    ===========================================================================
    """
    if not request.user.is_authenticated:
        return redirect('login')

    if not request.user.is_staff:
        messages.warning(request, "Acceso denegado: Solo el personal de coordinación puede crear cursos.")
        return redirect('catalogo')

    from .forms import CursoForm

    if request.method == 'POST':
        form = CursoForm(request.POST)
        if form.is_valid():
            curso = form.save()
            messages.success(request, f"¡El bootcamp '{curso.titulo}' ha sido publicado exitosamente en el catálogo!")
            return redirect('catalogo')
    else:
        form = CursoForm()

    return render(request, 'crear_curso.html', {'form': form})


def editar_curso_view(request, curso_id):
    """
    ===========================================================================
    VISTA FRONTEND: editar_curso_view
    ===========================================================================
    Permite a los administradores actualizar la información de un Bootcamp.

    SEGURIDAD Y ROLES:
    - Valida `request.user.is_staff` de forma estricta.

    LÓGICA DE ACTUALIZACIÓN:
    - get_object_or_404(): Si el curso_id no existe, lanza un 404 seguro en vez
      de un error 500.
    - instance=curso: Se pasa la instancia recuperada de la BD al `CursoForm`.
      Esto es VITAL: le indica a Django que haga un UPDATE (modificar existente)
      y no un INSERT (crear uno nuevo).
    ===========================================================================
    """
    if not request.user.is_authenticated:
        return redirect('login')

    if not request.user.is_staff:
        messages.warning(request, "Acceso denegado: Solo el personal de coordinación puede editar cursos.")
        return redirect('catalogo')

    curso = get_object_or_404(Curso, id=curso_id)
    from .forms import CursoForm

    if request.method == 'POST':
        form = CursoForm(request.POST, instance=curso)
        if form.is_valid():
            form.save()
            messages.success(request, f"¡El bootcamp '{curso.titulo}' ha sido actualizado exitosamente!")
            return redirect('catalogo')
    else:
        form = CursoForm(instance=curso)

    return render(request, 'editar_curso.html', {'form': form, 'curso': curso})


@login_required
@require_POST
def eliminar_curso_view(request, pk):
    """
    ===========================================================================
    VISTA FRONTEND: eliminar_curso_view
    ===========================================================================
    Vista blindada para eliminar cursos de la base de datos de forma segura.

    SEGURIDAD ESTRICTA:
    - @login_required: Obliga a tener sesión activa.
    - @require_POST: Solo acepta peticiones POST. Esto previene ataques CSRF o
      eliminaciones accidentales si alguien ingresa la URL por GET en el navegador.
    - is_staff: Restricción absoluta para usuarios sin rol de administración.

    LÓGICA DE ELIMINACIÓN Y DEPENDENCIAS (FOREIGN KEYS):
    Antes de eliminar el curso con `curso.delete()`, se envuelve el proceso en
    un bloque try-except. Si el ORM detecta relaciones huérfanas o falla el
    CASCADE, se atrapan excepciones (ProgrammingError). Como mecanismo final,
    se usa SQL crudo con parámetro seguro (`%s`) para evitar inyecciones SQL
    y borrar forzosamente el registro, superando bloqueos de base de datos.
    ===========================================================================
    """
    if not request.user.is_staff:
        messages.error(request, "Acceso denegado: No tienes permisos para eliminar cursos.")
        return redirect('catalogo')
        
    curso = get_object_or_404(Curso, pk=pk)
    titulo = curso.titulo
    
    try:
        # 1. Limpiar dependencias seguras antes de borrar (CarroItem, OrdenItem)
        # Esto previene bloqueos por llaves foráneas si existieran
        from .models import CarroItem, OrdenItem
        from django.db.utils import ProgrammingError, OperationalError
        
        try:
            CarroItem.objects.filter(curso=curso).delete()
        except (ProgrammingError, OperationalError):
            pass # Ignorar si la tabla no existe o hay problemas de DB
            
        try:
            OrdenItem.objects.filter(curso=curso).delete()
        except (ProgrammingError, OperationalError):
            pass # Ignorar si la tabla OrdenItem no existe en la DB

        # 2. Borrar el curso
        # Si Django aún falla (por ej. intenta hacer CASCADE en tablas huérfanas),
        # usamos SQL crudo como fallback definitivo para evitar el ProgrammingError.
        try:
            curso.delete()
        except (ProgrammingError, OperationalError):
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM cursos_curso WHERE id = %s", [curso.id])
                
        messages.success(request, f"El curso '{titulo}' ha sido eliminado correctamente.")
    except Exception as e:
        messages.error(request, f"Ocurrió un error al intentar eliminar el curso: {str(e)}")
        
    return redirect('catalogo')


def custom_404_view(request):
    """
    Vista catch-all: Renderiza el template 404.html para cualquier URL no encontrada.

    Se registra como la ÚLTIMA ruta en urls.py usando re_path(r'^.*$', ...).
    El regex r'^.*$' captura CUALQUIER URL que no haya coincidido con las
    rutas anteriores.

    status=404 es importante para que el navegador y buscadores sepan
    que la página no fue encontrada (semántica HTTP correcta).
    """
    return render(request, '404.html', status=404)
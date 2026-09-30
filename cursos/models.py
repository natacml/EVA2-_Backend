"""
================================================================================
ARCHIVO: cursos/models.py
================================================================================
PROPÓSITO:
    Define TODOS los modelos de datos (tablas de la base de datos) del sistema.
    Cada clase que hereda de models.Model se convierte en una tabla de PostgreSQL
    al ejecutar las migraciones (python manage.py makemigrations && migrate).

MODELOS IMPLEMENTADOS:
    1. CustomUser      - Usuario personalizado con campo 'rol' (Estudiante/Coordinador)
    2. Area            - Áreas temáticas que agrupan los cursos
    3. Curso           - Cursos/Bootcamps con cupos, costos y fechas
    4. CarroMatricula  - Carrito de compras persistente (1 por usuario)
    5. CarroItem       - Ítems individuales dentro del carrito
    6. MatriculaOrden  - Orden de matrícula con estado transaccional (PENDIENTE/PAGADO/CANCELADO)
    7. OrdenItem       - Ítems de la orden con precio congelado (snapshot histórico)

RELACIONES CLAVE:
    - CustomUser ←→ CarroMatricula: OneToOne (cada usuario tiene exactamente 1 carro)
    - CustomUser ←→ MatriculaOrden: ForeignKey (un usuario puede tener muchas órdenes)
    - Area ←→ Curso: ForeignKey (un área agrupa muchos cursos)
    - CarroMatricula ←→ CarroItem ←→ Curso: El carro contiene ítems que referencian cursos
    - MatriculaOrden ←→ OrdenItem ←→ Curso: La orden contiene ítems que referencian cursos

NOTA SOBRE CHOICES:
    Django permite definir opciones fijas para un campo usando CHOICES.
    Esto genera validación a nivel de formulario/serializer y una enumeración
    legible en el código. Se usa para 'rol' en CustomUser y 'estado' en MatriculaOrden.

LÓGICA DE INVENTARIO (REGLA CRÍTICA):
    El campo 'cupos_disponibles' de Curso actúa como el STOCK del sistema.
    - NO se descuenta al agregar un curso al carro.
    - SÍ se descuenta de forma ATÓMICA cuando la orden pasa a 'PAGADO'.
    - SÍ se REPONE si la orden pasa a 'CANCELADO'.
    Toda esta lógica transaccional se implementa en views.py, NO aquí.
================================================================================
"""

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings


# =============================================================================
# MODELO 1: CustomUser (Usuario Personalizado)
# =============================================================================
class CustomUser(AbstractUser):
    """
    Modelo de usuario personalizado que extiende AbstractUser de Django.

    ¿Por qué AbstractUser y no AbstractBaseUser?
    - AbstractUser INCLUYE todos los campos del User estándar de Django
      (username, email, password, first_name, last_name, is_active, is_staff, etc.)
      más toda la maquinaria de autenticación (hashing de passwords, permisos, etc.).
    - AbstractBaseUser solo provee el campo password y la lógica de hashing,
      obligando a implementar TODO lo demás manualmente.
    - Para nuestro caso, solo necesitamos AGREGAR el campo 'rol' y los apellidos,
      por lo que AbstractUser es la opción más eficiente y segura.

    CAMPOS PERSONALIZADOS:
    - rol: Define si el usuario es Estudiante ('EST') o Coordinador ('COO').
      Esto permite implementar control de acceso basado en roles (RBAC)
      en los permisos personalizados de la API.
    - apellido_paterno / apellido_materno: Separados para cumplir con la 3NF
      (Tercera Forma Normal) de normalización de base de datos.
    """

    # -------------------------------------------------------------------------
    # CHOICES para el campo 'rol'
    # -------------------------------------------------------------------------
    # ROL_CHOICES es una tupla de tuplas donde:
    # - El primer elemento ('EST', 'COO') es el valor almacenado en la BD.
    # - El segundo elemento ('Estudiante', 'Coordinador') es la etiqueta legible
    #   que se muestra en el admin y formularios.
    ROL_CHOICES = (
        ('EST', 'Estudiante'),             # Rol para alumnos que reservan cursos
        ('COO', 'Coordinador Académico'),   # Rol para administradores que gestionan cursos
    )

    # Campo 'rol': CharField con longitud máxima 3 (suficiente para 'EST'/'COO').
    # - choices=ROL_CHOICES: Restringe los valores aceptados a los definidos arriba.
    # - default='EST': Si no se especifica rol al crear el usuario, será Estudiante.
    rol = models.CharField(max_length=3, choices=ROL_CHOICES, default='EST', verbose_name='Rol')

    # Campos de apellido separados (3NF: cada dato atómico en su propio campo).
    # blank=True y null=True permiten que sean opcionales.
    apellido_paterno = models.CharField(max_length=100, blank=True, null=True, verbose_name='Apellido Paterno')
    apellido_materno = models.CharField(max_length=100, blank=True, null=True, verbose_name='Apellido Materno')

    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'
        # Orden por apellido paterno para listados administrativos
        ordering = ['apellido_paterno', 'first_name']

    def __str__(self):
        """
        Representación en string del usuario.
        get_rol_display() convierte 'EST' → 'Estudiante', 'COO' → 'Coordinador Académico'.
        """
        return f"{self.apellido_paterno or self.username} - {self.get_rol_display()}"


# =============================================================================
# MODELO 2: Area (Áreas de Conocimiento)
# =============================================================================
class Area(models.Model):
    """
    Representa un área temática que agrupa cursos relacionados.
    Ejemplos: "Desarrollo Web", "Data Science", "Cloud Computing".

    unique=True garantiza que no existan dos áreas con el mismo nombre.

    RELACIÓN: Un Area puede tener MUCHOS Cursos (relación 1:N inversa).
    """
    nombre = models.CharField(max_length=100, unique=True, verbose_name='Nombre del Área')

    class Meta:
        verbose_name = 'Área de Conocimiento'
        verbose_name_plural = 'Áreas de Conocimiento'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


# =============================================================================
# MODELO 3: Curso (Cursos y Bootcamps)
# =============================================================================
class Curso(models.Model):
    """
    Modelo central del negocio. Representa un curso o bootcamp disponible.

    LÓGICA DE INVENTARIO (IMPORTANTE PARA LA DEFENSA):
    El campo 'cupos_disponibles' actúa como el STOCK del sistema.
    - NO se descuenta al agregar un curso al carro (evita bloqueo de cupos).
    - SÍ se descuenta de forma ATÓMICA al pasar la orden a 'PAGADO'.
    - SÍ se repone si un coordinador cambia la orden a 'CANCELADO'.
    Esta lógica se implementa en views.py usando transaction.atomic() y F().

    CAMPOS:
    - area: ForeignKey al área temática (si se elimina el área, se eliminan sus cursos).
    - costo_matricula: DecimalField (no FloatField) para evitar errores de redondeo.
    - cupos_totales: Capacidad máxima original del curso.
    - cupos_disponibles: Stock actual que se modifica atómicamente.
    """
    area = models.ForeignKey(Area, on_delete=models.CASCADE, related_name='cursos', verbose_name='Área')
    titulo = models.CharField(max_length=200, verbose_name='Título')
    descripcion = models.TextField(verbose_name='Descripción')
    # DecimalField para dinero: max_digits=10, decimal_places=2 soporta hasta 99,999,999.99
    costo_matricula = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Costo de Matrícula')
    fecha_inicio = models.DateField(verbose_name='Fecha de Inicio')
    fecha_termino = models.DateField(verbose_name='Fecha de Término')
    cupos_totales = models.PositiveIntegerField(verbose_name='Cupos Totales')
    # cupos_disponibles: Este es el campo que se modifica con F() en las transacciones.
    cupos_disponibles = models.PositiveIntegerField(verbose_name='Cupos Disponibles')

    class Meta:
        verbose_name = 'Curso / Bootcamp'
        verbose_name_plural = 'Cursos y Bootcamps'
        ordering = ['fecha_inicio']

    def __str__(self):
        return self.titulo


# =============================================================================
# MODELO 4: CarroMatricula (Carrito de Compras Persistente)
# =============================================================================
class CarroMatricula(models.Model):
    """
    Carrito de matrícula persistente asociado 1:1 a un usuario.

    DISEÑO CLAVE (PARA LA DEFENSA):
    - OneToOneField: Cada usuario tiene EXACTAMENTE un carrito.
    - Persistencia post-logout: Al estar en la BD (no en la sesión HTTP),
      el carrito SOBREVIVE al cierre de sesión.
    - Se crea automáticamente al registrar al usuario (ver RegistroSerializer).
    """
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='carro', verbose_name='Estudiante'
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Carro de Matrícula'
        verbose_name_plural = 'Carros de Matrícula'

    def __str__(self):
        return f"Carro de {self.usuario.username}"


# =============================================================================
# MODELO 5: CarroItem (Ítems del Carrito)
# =============================================================================
class CarroItem(models.Model):
    """
    Un curso individual dentro del carrito.

    RESTRICCIÓN CLAVE (unique_together):
    Un usuario NO puede agregar el mismo curso dos veces al mismo carrito.
    unique_together = ('carro', 'curso') crea un índice UNIQUE compuesto
    en PostgreSQL. Si se intenta insertar un duplicado, PostgreSQL lanza
    IntegrityError.

    NOTA: Agregar un CarroItem NO descuenta cupos. Los cupos solo se
    descuentan al confirmar el pago (PagarOrdenView).
    """
    carro = models.ForeignKey(CarroMatricula, on_delete=models.CASCADE, related_name='items', verbose_name='Carro')
    curso = models.ForeignKey(Curso, on_delete=models.SET_NULL, null=True, blank=True, related_name='en_carros', verbose_name='Curso')
    agregado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Ítem de Carro'
        verbose_name_plural = 'Ítems de Carro'
        # =====================================================================
        # unique_together: RESTRICCIÓN DE UNICIDAD COMPUESTA
        # =====================================================================
        # Crea un índice UNIQUE en PostgreSQL sobre la combinación (carro, curso).
        # Impide a nivel de BD que un mismo curso aparezca dos veces en un carrito.
        unique_together = ('carro', 'curso')

    def __str__(self):
        return f"{self.curso.titulo} en carro de {self.carro.usuario.username}"


# =============================================================================
# MODELO 6: MatriculaOrden (Orden de Matrícula con Estado Transaccional)
# =============================================================================
class MatriculaOrden(models.Model):
    """
    Orden de matrícula con ciclo de vida basado en ESTADO.

    CICLO DE VIDA DEL ESTADO (PARA LA DEFENSA):
    =============================================
    1. 'PENDIENTE': Estado inicial al hacer checkout del carro.
       Los cupos NO se descuentan en este estado (el estudiante aún no ha pagado).

    2. 'PAGADO': El estudiante confirma el pago.
       Los cupos se DESCUENTAN atómicamente con transaction.atomic() + F().
       Si no hay cupos suficientes, se rechaza la operación.

    3. 'CANCELADO': Un coordinador cancela la orden.
       Si la orden estaba en 'PAGADO', los cupos se REPONEN automáticamente.
       Si estaba en 'PENDIENTE', no hay cupos que reponer.

    TRANSACCIONALIDAD:
    Todos los cambios de estado se realizan dentro de transaction.atomic()
    para garantizar que si algo falla, TODA la operación se revierte.

    RELACIONES:
    - ForeignKey a CustomUser (N:1): Un usuario puede tener muchas órdenes.
    - MatriculaOrden ← OrdenItem (1:N): Una orden contiene muchos ítems.
    """

    # -------------------------------------------------------------------------
    # CHOICES para el campo 'estado'
    # -------------------------------------------------------------------------
    # Define los 3 estados posibles de una orden de matrícula.
    # El primer valor de cada tupla se almacena en la BD.
    # El segundo valor es la etiqueta legible para el usuario.
    ESTADO_CHOICES = (
        ('PENDIENTE', 'Pendiente'),     # Orden creada, sin pagar
        ('PAGADO', 'Pagado'),           # Orden pagada, cupos descontados
        ('CANCELADO', 'Cancelado'),     # Orden cancelada, cupos repuestos (si aplica)
    )

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='ordenes', verbose_name='Estudiante'
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')

    # Campo 'estado' con CHOICES.
    # max_length=10 para acomodar 'CANCELADO' (9 caracteres).
    # default='PENDIENTE': Toda orden nace en estado pendiente.
    estado = models.CharField(
        max_length=10, choices=ESTADO_CHOICES, default='PENDIENTE', verbose_name='Estado'
    )

    class Meta:
        verbose_name = 'Orden de Matrícula'
        verbose_name_plural = 'Órdenes de Matrícula'
        # Ordena de más reciente a más antigua
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f"Orden #{self.pk} - {self.usuario.username} ({self.get_estado_display()})"


# =============================================================================
# MODELO 7: OrdenItem (Ítems de la Orden con Precio Histórico)
# =============================================================================
class OrdenItem(models.Model):
    """
    Curso individual dentro de una orden de matrícula.

    ¿POR QUÉ SEPARAR OrdenItem DE CarroItem?
    Porque son conceptos diferentes:
    - CarroItem es TEMPORAL y EDITABLE (el usuario puede agregar/quitar cursos).
    - OrdenItem es PERMANENTE e INMUTABLE (registro histórico de la compra).

    CAMPO 'precio_al_matricular':
    Almacena el precio del curso AL MOMENTO de crear la orden (snapshot).
    Si el coordinador cambia el precio del curso después, este campo
    preserva lo que el estudiante pagó originalmente.
    """
    orden = models.ForeignKey(
        MatriculaOrden, on_delete=models.CASCADE,
        related_name='items', verbose_name='Orden'
    )
    curso = models.ForeignKey(
        Curso, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='en_ordenes', verbose_name='Curso'
    )
    # Precio congelado: snapshot del costo_matricula al momento de la orden
    precio_al_matricular = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name='Precio Histórico'
    )

    class Meta:
        verbose_name = 'Ítem de Orden'
        verbose_name_plural = 'Ítems de Orden'

    def __str__(self):
        return f"{self.curso.titulo} (Orden #{self.orden.pk})"
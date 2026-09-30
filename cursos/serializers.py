"""
================================================================================
ARCHIVO: cursos/serializers.py
================================================================================
PROPÓSITO:
    Los serializers son la capa intermedia entre los MODELOS (Python/Django) y
    la API REST (JSON). Cumplen DOS funciones:

    1. SERIALIZACIÓN (Salida): Modelo Python → JSON para la respuesta HTTP.
    2. DESERIALIZACIÓN + VALIDACIÓN (Entrada): JSON del request → objeto Python.

SERIALIZERS IMPLEMENTADOS:
    1. CustomTokenObtainPairSerializer - JWT personalizado con claim 'rol'
    2. RegistroSerializer              - Registro de usuarios con password hasheado
    3. AreaSerializer                  - CRUD de áreas
    4. CursoSerializer                 - Lectura de cursos con área nombre
    5. CarroItemSerializer             - Ítems del carro con datos del curso
    6. CarroMatriculaSerializer        - Carro completo con ítems anidados
    7. OrdenItemSerializer             - Ítems de la orden con precio histórico
    8. MatriculaOrdenSerializer        - Orden completa con estado, total e ítems
================================================================================
"""

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import CustomUser, Area, Curso, CarroMatricula, CarroItem, MatriculaOrden, OrdenItem


# =============================================================================
# SERIALIZER 1: CustomTokenObtainPairSerializer (JWT con Claim 'rol')
# =============================================================================
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Personaliza el token JWT para incluir el rol del usuario en los claims.

    ¿QUÉ ES UN CLAIM?
    Un JWT tiene 3 partes: Header, Payload y Signature.
    El Payload contiene "claims" (afirmaciones) sobre el usuario.
    Por defecto SimpleJWT incluye: user_id, exp, token_type.
    Nosotros AGREGAMOS 'rol' y 'username' para que el frontend
    pueda saber el rol sin hacer un request adicional.

    CONFIGURACIÓN: En settings.py:
    SIMPLE_JWT = { 'TOKEN_OBTAIN_SERIALIZER': 'cursos.serializers.CustomTokenObtainPairSerializer' }
    """
    @classmethod
    def get_token(cls, user):
        """
        Genera el token JWT e inyecta claims personalizados.
        Se llama internamente cuando el usuario hace login (POST /api/token/).
        """
        token = super().get_token(user)
        # Agregamos 'rol' y 'username' al payload del JWT
        token['rol'] = user.rol
        token['username'] = user.username
        return token


# =============================================================================
# SERIALIZER 2: RegistroSerializer (Registro de Nuevos Usuarios)
# =============================================================================
class RegistroSerializer(serializers.ModelSerializer):
    """
    Serializer para el registro de nuevos usuarios.

    CAMPO 'password':
    write_only=True → NUNCA aparece en las respuestas JSON (seguridad).

    MÉTODO create():
    Usa set_password() para HASHEAR el password en vez de guardarlo en texto plano.
    También crea el CarroMatricula automáticamente al registrar al usuario.
    """
    # write_only=True: El password solo se acepta en el request, nunca sale en la respuesta.
    password = serializers.CharField(write_only=True)

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'password', 'first_name', 'last_name', 'apellido_paterno', 'apellido_materno', 'rol']

    def create(self, validated_data):
        """
        Sobreescribimos create() para:
        1. Extraer el password de los datos validados.
        2. Crear el usuario SIN password en texto plano.
        3. Hashear el password con set_password() (usa PBKDF2 de Django).
        4. Crear el CarroMatricula asociado automáticamente.

        ¿POR QUÉ set_password() y no asignar directamente?
        user.password = "123" → guarda en TEXTO PLANO (INSEGURO).
        user.set_password("123") → guarda el HASH (SEGURO).
        Sin hashing, el login nunca funcionaría porque Django compara hashes.
        """
        password = validated_data.pop('password')
        user = CustomUser(**validated_data)
        user.set_password(password)  # Hashea el password con PBKDF2
        user.save()
        # Crear el carro de matrícula automáticamente al registrar
        CarroMatricula.objects.create(usuario=user)
        return user


# =============================================================================
# SERIALIZER 3: AreaSerializer
# =============================================================================
class AreaSerializer(serializers.ModelSerializer):
    """
    Serializer simple para el modelo Area.
    '__all__' incluye todos los campos: id, nombre.
    ModelSerializer genera validadores automáticos (unique para nombre, etc.).
    """
    class Meta:
        model = Area
        fields = '__all__'


# =============================================================================
# SERIALIZER 4: CursoSerializer
# =============================================================================
class CursoSerializer(serializers.ModelSerializer):
    """
    Serializer de lectura para cursos.

    Incluye 'area_nombre' como campo calculado (SerializerMethodField)
    para que el frontend pueda mostrar el nombre del área sin navegar
    la relación ForeignKey.

    Ejemplo de respuesta:
    { "id": 1, "area": 1, "area_nombre": "Desarrollo Web", "titulo": "...", ... }
    """
    # SerializerMethodField: campo de solo lectura cuyo valor se obtiene
    # llamando al método get_area_nombre()
    area_nombre = serializers.SerializerMethodField()

    class Meta:
        model = Curso
        fields = '__all__'

    def get_area_nombre(self, obj) -> str:
        """Retorna el nombre del área asociada al curso."""
        return obj.area.nombre


# =============================================================================
# SERIALIZER 5: CarroItemSerializer (Ítems del Carrito)
# =============================================================================
class CarroItemSerializer(serializers.ModelSerializer):
    """
    Serializer para ítems individuales del carrito.

    Incluye campos de solo lectura (ReadOnlyField) que extraen datos
    del curso relacionado usando la notación 'source':
    - source='curso.titulo' → navega la FK y obtiene el título.
    - source='curso.costo_matricula' → obtiene el costo.

    Esto evita que el frontend tenga que hacer un request adicional
    para obtener los datos del curso.
    """
    curso_titulo = serializers.ReadOnlyField(source='curso.titulo')
    curso_costo = serializers.ReadOnlyField(source='curso.costo_matricula')

    class Meta:
        model = CarroItem
        fields = ['id', 'curso', 'curso_titulo', 'curso_costo', 'agregado_en']


# =============================================================================
# SERIALIZER 6: CarroMatriculaSerializer (Carrito Completo)
# =============================================================================
class CarroMatriculaSerializer(serializers.ModelSerializer):
    """
    Serializer del carrito completo con ítems anidados.

    items = CarroItemSerializer(many=True) anida la lista completa de
    ítems del carrito dentro de la respuesta JSON.
    many=True indica que es una relación 1:N (un carro tiene muchos ítems).
    read_only=True porque los ítems se crean/eliminan en endpoints separados.
    """
    items = CarroItemSerializer(many=True, read_only=True)

    class Meta:
        model = CarroMatricula
        fields = ['id', 'usuario', 'creado_en', 'items']


# =============================================================================
# SERIALIZER 7: OrdenItemSerializer (Ítems de la Orden)
# =============================================================================
class OrdenItemSerializer(serializers.ModelSerializer):
    """
    Serializer para ítems individuales de una orden de matrícula.

    Incluye 'curso_titulo' como ReadOnlyField para facilitar la lectura.
    El campo 'precio_al_matricular' muestra el precio CONGELADO (snapshot)
    que se registró al momento del checkout, NO el precio actual del curso.
    """
    curso_titulo = serializers.ReadOnlyField(source='curso.titulo')

    class Meta:
        model = OrdenItem
        fields = ['id', 'curso', 'curso_titulo', 'precio_al_matricular']


# =============================================================================
# SERIALIZER 8: MatriculaOrdenSerializer (Orden Completa)
# =============================================================================
class MatriculaOrdenSerializer(serializers.ModelSerializer):
    """
    Serializer de la orden de matrícula completa con ítems, estado y total.

    CAMPOS CALCULADOS:
    - estado_display: Convierte 'PAGADO' → 'Pagado' (etiqueta legible).
    - total: Suma de los precios_al_matricular de todos los ítems.

    ÍTEMS ANIDADOS:
    - items: Lista de OrdenItemSerializer con precio histórico de cada curso.

    Ejemplo de respuesta:
    {
        "id": 1,
        "usuario": 3,
        "fecha_creacion": "2026-09-29T12:00:00Z",
        "estado": "PAGADO",
        "estado_display": "Pagado",
        "total": 750000.00,
        "items": [
            { "id": 1, "curso": 5, "curso_titulo": "Bootcamp React", "precio_al_matricular": "350000.00" },
            { "id": 2, "curso": 8, "curso_titulo": "Data Science", "precio_al_matricular": "400000.00" }
        ]
    }
    """
    items = OrdenItemSerializer(many=True, read_only=True)
    # SerializerMethodField: campo calculado que llama a get_estado_display()
    estado_display = serializers.SerializerMethodField()
    # Total calculado sumando los precios históricos de cada ítem
    total = serializers.SerializerMethodField()

    class Meta:
        model = MatriculaOrden
        fields = ['id', 'usuario', 'fecha_creacion', 'estado', 'estado_display', 'total', 'items']

    def get_estado_display(self, obj) -> str:
        """
        Retorna la etiqueta legible del estado CHOICES.
        Django genera automáticamente get_<campo>_display() para campos con CHOICES:
        'PENDIENTE' → 'Pendiente', 'PAGADO' → 'Pagado', 'CANCELADO' → 'Cancelado'.
        """
        return obj.get_estado_display()

    def get_total(self, obj) -> float:
        """
        Calcula el total de la orden sumando los precios HISTÓRICOS (snapshot).
        Usamos precio_al_matricular (no curso.costo_matricula) porque el precio
        del curso puede haber cambiado después de la matrícula.
        """
        return sum(item.precio_al_matricular for item in obj.items.all())
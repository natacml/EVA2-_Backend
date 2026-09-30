from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    CustomUser, Area, Curso,
    CarroMatricula, CarroItem,
    MatriculaOrden, OrdenItem
)


# =============================================================================
# ADMIN PARA CustomUser
# =============================================================================
# Extendemos UserAdmin para que el panel de admin muestre nuestro campo 'rol'
# junto con los campos estándar de Django (username, email, password, etc.).
@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    """
    Configuración del admin para el modelo CustomUser.
    Hereda de UserAdmin para mantener toda la funcionalidad del admin
    de usuarios estándar de Django (cambio de contraseña, filtros, etc.)
    y agrega el campo 'rol' a las secciones correspondientes.
    """
    # list_display: Columnas visibles en la lista de usuarios.
    list_display = ('username', 'email', 'rol', 'is_active', 'is_staff')

    # list_filter: Filtros laterales en la lista de usuarios.
    list_filter = ('rol', 'is_active', 'is_staff')

    # fieldsets: Secciones del formulario de edición de usuario.
    # Agregamos 'rol' a la sección de 'Información personal'.
    fieldsets = UserAdmin.fieldsets + (
        ('Información de Rol', {'fields': ('rol',)}),
    )

    # add_fieldsets: Campos que aparecen al CREAR un nuevo usuario desde el admin.
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Información de Rol', {'fields': ('rol',)}),
    )


# =============================================================================
# ADMIN PARA LOS DEMÁS MODELOS
# =============================================================================
@admin.register(Area)
class AreaAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre')
    search_fields = ('nombre',)


@admin.register(Curso)
class CursoAdmin(admin.ModelAdmin):
    list_display = ('id', 'titulo', 'area', 'costo_matricula', 'cupos_disponibles', 'fecha_inicio')
    list_filter = ('area', 'fecha_inicio')
    search_fields = ('titulo', 'descripcion')


@admin.register(CarroMatricula)
class CarroMatriculaAdmin(admin.ModelAdmin):
    list_display = ('id', 'usuario', 'creado_en')


@admin.register(CarroItem)
class CarroItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'carro', 'curso', 'agregado_en')
    list_filter = ('carro',)


@admin.register(MatriculaOrden)
class MatriculaOrdenAdmin(admin.ModelAdmin):
    list_display = ('id', 'usuario', 'estado', 'fecha_creacion')
    list_filter = ('estado',)


@admin.register(OrdenItem)
class OrdenItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'orden', 'curso', 'precio_al_matricular')

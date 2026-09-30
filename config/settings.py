"""
================================================================================
ARCHIVO: config/settings.py
================================================================================
PROPÓSITO:
    Este archivo es el corazón de la configuración del proyecto Django.
    Aquí se definen TODAS las variables que controlan el comportamiento
    del framework: base de datos, aplicaciones instaladas, middleware,
    autenticación, JWT, documentación API, etc.

DECISIONES DE DISEÑO:
    - Se usa PostgreSQL como motor de base de datos (requisito de la rúbrica).
    - Se configura un modelo de usuario personalizado (CustomUser) mediante
      AUTH_USER_MODEL para poder extender AbstractUser con el campo 'rol'.
    - Se integra SimpleJWT para autenticación stateless basada en tokens.
    - Se usa drf-spectacular para la generación automática de documentación
      OpenAPI/Swagger.
    - Se usa django-filter para habilitar filtrado en los endpoints públicos.

NOTA IMPORTANTE:
    AUTH_USER_MODEL = 'cursos.CustomUser' DEBE definirse ANTES de ejecutar
    la primera migración. Cambiarlo después rompe las tablas de Django.
================================================================================
"""

from pathlib import Path
from datetime import timedelta

# =============================================================================
# RUTA BASE DEL PROYECTO
# =============================================================================
BASE_DIR = Path(__file__).resolve().parent.parent


# =============================================================================
# SEGURIDAD
# =============================================================================
SECRET_KEY = 'django-insecure-^2yfl&8!9*3y#@y9q3x3&ne8se6#!v*zyaglz-ee=*o1fh9@u='

DEBUG = True

ALLOWED_HOSTS = ['*']


# =============================================================================
# APLICACIONES INSTALADAS (INSTALLED_APPS)
# =============================================================================
INSTALLED_APPS = [
    # --- Apps nativas de Django ---
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # --- Apps de terceros ---
    'rest_framework',
    'django_filters',
    'rest_framework_simplejwt',
    'drf_spectacular',

    # --- Apps propias del proyecto ---
    'cursos',
]


# =============================================================================
# MIDDLEWARE
# =============================================================================
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


# =============================================================================
# CONFIGURACIÓN DE URLs Y TEMPLATES
# =============================================================================
ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# =============================================================================
# BASE DE DATOS - POSTGRESQL
# =============================================================================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'edtech_reservas',
        'USER': 'postgres',
        'PASSWORD': '123',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}


# =============================================================================
# MODELO DE USUARIO PERSONALIZADO
# =============================================================================
AUTH_USER_MODEL = 'cursos.CustomUser'


# =============================================================================
# VALIDADORES DE CONTRASEÑA
# =============================================================================
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# =============================================================================
# INTERNACIONALIZACIÓN
# =============================================================================
LANGUAGE_CODE = 'es-cl'

TIME_ZONE = 'America/Santiago'

USE_I18N = True

USE_TZ = True


# =============================================================================
# ARCHIVOS ESTÁTICOS
# =============================================================================
STATIC_URL = 'static/'


# =============================================================================
# DEFAULT_AUTO_FIELD
# =============================================================================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# =============================================================================
# CONFIGURACIÓN DE DJANGO REST FRAMEWORK (DRF)
# =============================================================================
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.AllowAny',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}


# =============================================================================
# CONFIGURACIÓN DE SIMPLE JWT
# =============================================================================
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'TOKEN_OBTAIN_SERIALIZER': 'cursos.serializers.CustomTokenObtainPairSerializer',
}


# =============================================================================
# CONFIGURACIÓN DE DRF-SPECTACULAR (SWAGGER / OPENAPI)
# =============================================================================
SPECTACULAR_SETTINGS = {
    'TITLE': 'Plataforma de Reservas de Cursos y Bootcamps (EdTech) - API',
    'DESCRIPTION': (
        'API REST para la gestión de matrículas EdTech. '
        'Incluye catálogo público, carro persistente, control de stock y JWT.\n\n'
        '---\n'
        '**DATOS DEL ALUMNO (EVALUACIÓN 2)**\n'
        '* **Nombre Completo:** Natalia Arriagada\n'
        '* **Sección:** Sección AP-N4-C2\n'
        '* **Año:** 2026\n'
    ),
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}


# =============================================================================
# REDIRECCIONES DE AUTENTICACIÓN
# =============================================================================
LOGIN_REDIRECT_URL = 'catalogo'
LOGOUT_REDIRECT_URL = 'logout'
LOGIN_URL = 'login'

"""
Django settings for ResolveAI project.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from django.core.management.utils import get_random_secret_key

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / '.env')


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def env_list(name: str, default: str = '') -> list[str]:
    return [
        value.strip()
        for value in os.environ.get(name, default).split(',')
        if value.strip()
    ]


# Security
DEBUG = env_bool('DJANGO_DEBUG', default=False)
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '').strip()
if not SECRET_KEY:
    SECRET_KEY = get_random_secret_key()

ALLOWED_HOSTS = env_list('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1')
CSRF_TRUSTED_ORIGINS = env_list(
    'DJANGO_CSRF_TRUSTED_ORIGINS',
    'http://localhost:5173,http://localhost:5174,'
    'http://127.0.0.1:5173,http://127.0.0.1:5174',
)

SECURE_SSL_REDIRECT = env_bool('DJANGO_SECURE_SSL_REDIRECT')
SESSION_COOKIE_SECURE = env_bool('DJANGO_SESSION_COOKIE_SECURE')
CSRF_COOKIE_SECURE = env_bool('DJANGO_CSRF_COOKIE_SECURE')
SECURE_HSTS_SECONDS = int(
    os.environ.get('DJANGO_SECURE_HSTS_SECONDS', '0')
)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool(
    'DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS',
)
SECURE_HSTS_PRELOAD = env_bool('DJANGO_SECURE_HSTS_PRELOAD')
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'

if env_bool('DJANGO_BEHIND_PROXY'):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')


# Applications
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'rest_framework',
    'corsheaders',

    'accounts',
    'tickets',
    'ai_engine',
    'knowledge_base',
]


# Middleware
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


# URL and application configuration
ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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


# Database
# PostgreSQL is used when POSTGRES_DB is configured.
# SQLite is the local fallback.

if os.environ.get('POSTGRES_DB'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ['POSTGRES_DB'],
            'USER': os.environ.get('POSTGRES_USER', ''),
            'PASSWORD': os.environ.get('POSTGRES_PASSWORD', ''),
            'HOST': os.environ.get('POSTGRES_HOST', 'localhost'),
            'PORT': os.environ.get('POSTGRES_PORT', '5432'),
            'CONN_MAX_AGE': int(os.environ.get('POSTGRES_CONN_MAX_AGE', '60')),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


# Password validation
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


# Internationalization
LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static and media files
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# CORS
CORS_ALLOWED_ORIGINS = env_list(
    'DJANGO_CORS_ALLOWED_ORIGINS',
    ','.join(CSRF_TRUSTED_ORIGINS),
)


# RAG configuration
RAG_CONFIG = {
    'VECTOR_BACKEND': os.environ.get(
        'RAG_VECTOR_BACKEND',
        'pgvector' if os.environ.get('POSTGRES_DB') else 'numpy',
    ),
    'EMBEDDING_MODEL': os.environ.get(
        'RAG_EMBEDDING_MODEL',
        'sentence-transformers/all-MiniLM-L6-v2',
    ),
    'EMBEDDING_DIMENSIONS': int(
        os.environ.get('RAG_EMBEDDING_DIMENSIONS', '384')
    ),
    'EMBEDDING_BATCH_SIZE': int(
        os.environ.get('RAG_EMBEDDING_BATCH_SIZE', '32')
    ),
    'MAX_DOCUMENT_SIZE_MB': int(
        os.environ.get('RAG_MAX_DOCUMENT_SIZE_MB', '10')
    ),
    'CHUNK_SIZE': int(
        os.environ.get('RAG_CHUNK_SIZE', '2000')
    ),
    'CHUNK_OVERLAP': int(
        os.environ.get('RAG_CHUNK_OVERLAP', '200')
    ),
    'RETRIEVAL_TOP_K': int(
        os.environ.get('RAG_RETRIEVAL_TOP_K', '5')
    ),
    'RETRIEVAL_MIN_SIMILARITY': float(
        os.environ.get('RAG_RETRIEVAL_MIN_SIMILARITY', '0.0')
    ),
    'MAX_QUESTION_LENGTH': int(
        os.environ.get('RAG_MAX_QUESTION_LENGTH', '2000')
    ),
    'CONTEXT_MAX_CHARS': int(
        os.environ.get('RAG_CONTEXT_MAX_CHARS', '12000')
    ),
    'LLM_PROVIDER': os.environ.get(
        'RAG_LLM_PROVIDER',
        'disabled',
    ),
}


# Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
}


# Email
MAILERS = {
    'default': {
        'BACKEND': os.environ.get(
            'EMAIL_BACKEND',
            'django.core.mail.backends.console.EmailBackend'
            if DEBUG else 'django.core.mail.backends.smtp.EmailBackend',
        ),
        'HOST': os.environ.get('EMAIL_HOST', ''),
        'PORT': int(os.environ.get('EMAIL_PORT', '587')),
        'USERNAME': os.environ.get('EMAIL_HOST_USER', ''),
        'PASSWORD': os.environ.get('EMAIL_HOST_PASSWORD', ''),
        'USE_TLS': env_bool('EMAIL_USE_TLS', default=not DEBUG),
        'USE_SSL': env_bool('EMAIL_USE_SSL'),
    },
}

DEFAULT_FROM_EMAIL = os.environ.get(
    'DEFAULT_FROM_EMAIL',
    'webmaster@localhost',
)


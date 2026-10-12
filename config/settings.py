"""Configuration du service Équipes : tout vient des variables d'environnement."""
import os

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-change-me")
DEBUG = os.getenv("DEBUG", "0") == "1"
ALLOWED_HOSTS = ["*"]  # service joignable uniquement sur le réseau Docker interne

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "equipes")
POKEDEX_URL = os.getenv("POKEDEX_URL", "http://localhost:8000")

INSTALLED_APPS = ["rest_framework", "teams"]
MIDDLEWARE = ["django.middleware.common.CommonMiddleware"]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
APPEND_SLASH = False

# Pas d'ORM ici : MongoDB est piloté directement avec pymongo (cf. ADR)
DATABASES = {}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}

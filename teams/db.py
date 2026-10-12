"""Accès à MongoDB. Une équipe = un document, lu et écrit d'un seul bloc."""
from django.conf import settings
from pymongo import MongoClient

_client = None


def teams_collection():
    global _client
    if _client is None:
        _client = MongoClient(settings.MONGO_URL)
    col = _client[settings.MONGO_DB]["teams"]
    col.create_index("userId")
    return col

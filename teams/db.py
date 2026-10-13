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


def captures_collection():
    """Progression du mode Capture : un document par dresseur (Pokémon débloqués, victoires, run)."""
    teams_collection()
    col = _client[settings.MONGO_DB]["captures"]
    col.create_index("userId", unique=True)
    return col


def unlocked_of(uids) -> dict:
    """Pokémon débloqués par dresseur ({userId: [...]}) ; liste vide si pas encore commencé."""
    uids = list(set(uids))
    found = {d["userId"]: d["unlocked"] for d in captures_collection().find({"userId": {"$in": uids}})}
    return {u: found.get(u, []) for u in uids}

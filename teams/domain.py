"""Règles métier des équipes, indépendantes de Django et de MongoDB."""

MAX_MEMBERS = 6
MAX_MEGAS = 1  # règle officielle : une seule Méga-Évolution par équipe


def extract_pokemon_ids(data: dict) -> list:
    """Le front envoie poke1..poke6 (format hérité du monolithe)."""
    ids = [data.get(f"poke{i}") for i in range(1, MAX_MEMBERS + 1)]
    return [pid for pid in ids if pid not in (None, "", 0)]


def snapshot(profile: dict) -> dict:
    """Instantané d'un Pokémon au moment de la création (cf. ADR référence vs copie)."""
    return {
        "pokemonId": profile["id"],
        "name": profile["name"],
        "isMega": profile.get("isMega", False),
        "isForm": profile.get("isForm", False),
        "baseSpecies": profile.get("baseSpecies") or profile["name"],
        "sprite": profile["sprite"],
        "types": profile["types"],
        "stats": profile["stats"],
        "statTotal": profile["statTotal"],
        "weaknesses": profile["weaknesses"],
        "resistances": profile["resistances"],
    }


def check_species(profiles: list[dict]):
    """Species Clause : une seule fois chaque espèce par équipe
    (une Méga compte comme son espèce de base : Dracaufeu + Méga-Dracaufeu X est refusé)."""
    seen = set()
    for p in profiles:
        species = p.get("baseSpecies") or p["name"]
        if species in seen:
            return f"Un seul exemplaire de chaque Pokémon par équipe ({species})"
        seen.add(species)
    return None


def check_megas(profiles: list[dict]):
    """Renvoie un message d'erreur si l'équipe viole la règle des Méga, sinon None."""
    megas = [p["name"] for p in profiles if p.get("isMega")]
    if len(megas) > MAX_MEGAS:
        return f"Une seule Méga-Évolution par équipe ({', '.join(megas)})"
    return None


def to_api(doc: dict) -> dict:
    """Format renvoyé au front : idTeam, nom et poke1..poke6 restent compatibles."""
    members = doc["members"]
    out = {
        "idTeam": str(doc["_id"]),
        "nom": doc["nom"],
        "typePrincipal": doc.get("typePrincipal", ""),
        "isPublic": doc.get("isPublic", False),
        "userId": doc["userId"],
        "members": members,
        "summary": doc["summary"],
    }
    for i in range(MAX_MEMBERS):
        out[f"poke{i + 1}"] = members[i]["pokemonId"] if i < len(members) else None
    return out

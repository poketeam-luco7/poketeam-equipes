"""Règles métier des équipes, indépendantes de Django et de MongoDB."""

MAX_MEMBERS = 6


def extract_pokemon_ids(data: dict) -> list:
    """Le front envoie poke1..poke6 (format hérité du monolithe)."""
    ids = [data.get(f"poke{i}") for i in range(1, MAX_MEMBERS + 1)]
    return [pid for pid in ids if pid not in (None, "", 0)]


def snapshot(profile: dict) -> dict:
    """Instantané d'un Pokémon au moment de la création (cf. ADR référence vs copie)."""
    return {
        "pokemonId": profile["id"],
        "name": profile["name"],
        "sprite": profile["sprite"],
        "types": profile["types"],
        "stats": profile["stats"],
        "statTotal": profile["statTotal"],
        "weaknesses": profile["weaknesses"],
        "resistances": profile["resistances"],
    }


def build_summary(members: list[dict]) -> dict:
    """Chaque Pokémon ajoute +1 dans chacune de ses faiblesses et résistances."""
    weak, resist, offensive = {}, {}, []
    for m in members:
        for t in m["weaknesses"]:
            weak[t] = weak.get(t, 0) + 1
        for t in m["resistances"]:
            resist[t] = resist.get(t, 0) + 1
        for t in m["types"]:
            if t not in offensive:
                offensive.append(t)
    return {
        "statTotal": sum(m["statTotal"] for m in members),
        "weak": weak,
        "resist": resist,
        "offensiveTypes": offensive,
    }


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

"""Client du service Pokédex (appel interne direct, sans passer par la gateway)."""
import httpx
from django.conf import settings


class PokemonInconnu(Exception):
    pass


class PokedexIndisponible(Exception):
    pass


class PokedexRefus(Exception):
    """Le Pokédex refuse l'action (règle du jeu) : le message est à montrer au dresseur."""


def _post(path: str, body: dict) -> httpx.Response:
    try:
        return httpx.post(f"{settings.POKEDEX_URL}{path}", json=body, timeout=30)
    except httpx.HTTPError as e:
        raise PokedexIndisponible() from e


def analyze(pokemon_ids: list) -> dict:
    """Profils des membres (dans l'ordre) + summary, calculés par le Pokédex.
    Le service Équipes ne contient ainsi aucune règle de type Pokémon."""
    r = _post("/teams/analyze", {"pokemonIds": pokemon_ids})
    if r.status_code == 404:
        raise PokemonInconnu(r.json().get("detail", "").split(": ")[-1])
    if r.status_code != 200:
        raise PokedexIndisponible()
    return r.json()


def compare(team_a: dict, team_b: dict) -> dict:
    r = _post("/teams/compare", {"teamA": team_a, "teamB": team_b})
    if r.status_code != 200:
        raise PokedexIndisponible()
    return r.json()


def fight_boss(team: dict) -> dict:
    r = _post("/boss/fight", {"team": team})
    if r.status_code == 400:
        raise PokedexRefus(r.json().get("detail", "Combat refusé"))
    if r.status_code != 200:
        raise PokedexIndisponible()
    return r.json()


# --- Mode Capture -------------------------------------------------------------------

def _post_json(path: str, body: dict) -> dict:
    r = _post(path, body)
    if r.status_code == 404:
        raise PokemonInconnu(r.json().get("detail", ""))
    if r.status_code != 200:
        raise PokedexIndisponible()
    return r.json()


def _get_json(path: str):
    try:
        r = httpx.get(f"{settings.POKEDEX_URL}{path}", timeout=30)
    except httpx.HTTPError as e:
        raise PokedexIndisponible() from e
    if r.status_code != 200:
        raise PokedexIndisponible()
    return r.json()


def capture_starters() -> list:
    return _get_json("/capture/starters")


def capture_state(unlocked: list, victories: dict) -> dict:
    return _post_json("/capture/state", {"unlocked": unlocked, "victories": victories})


def capture_encounters(tier: int, unlocked: list, exclude: list) -> dict:
    """{training, candidates}"""
    return _post_json("/capture/encounters", {"tier": tier, "unlocked": unlocked, "exclude": exclude})


def capture_analyze(pokemon_ids: list, unlocked: list, tier: int | None = None) -> dict:
    body = {"pokemonIds": pokemon_ids, "unlocked": unlocked}
    if tier is not None:
        body["tier"] = tier
    return _post_json("/capture/analyze", body)


def capture_fight(team: dict, wild_id: int, team_size: int) -> dict:
    return _post_json("/capture/fight", {"team": team, "wildId": wild_id, "teamSize": team_size})


def capture_locked(teams: dict) -> dict:
    """{clé: {pokemonIds, unlocked}} -> {clé: [Pokémon non débloqués]}"""
    return _post_json("/capture/locked", {"teams": teams})


# --- Donjons ------------------------------------------------------------------------

def dungeons_state(unlocked: list) -> dict:
    return _post_json("/dungeons/state", {"unlocked": unlocked})


def dungeon_fight(team: dict, dungeon_id: int, unlocked: list) -> dict:
    r = _post("/dungeons/fight", {"team": team, "dungeonId": dungeon_id, "unlocked": unlocked})
    if r.status_code == 400:
        raise PokedexRefus(r.json().get("detail", "Entrée refusée"))
    if r.status_code == 404:
        raise PokemonInconnu(r.json().get("detail", ""))
    if r.status_code != 200:
        raise PokedexIndisponible()
    return r.json()

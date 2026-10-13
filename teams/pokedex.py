"""Client du service Pokédex (appel interne direct, sans passer par la gateway)."""
import httpx
from django.conf import settings


class PokemonInconnu(Exception):
    pass


class PokedexIndisponible(Exception):
    pass


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

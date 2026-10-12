"""Client du service Pokédex (appel interne direct, sans passer par la gateway)."""
from concurrent.futures import ThreadPoolExecutor

import httpx
from django.conf import settings


class PokemonInconnu(Exception):
    pass


class PokedexIndisponible(Exception):
    pass


def _get_profile(pokemon_id) -> dict:
    try:
        r = httpx.get(f"{settings.POKEDEX_URL}/pokemon/{pokemon_id}", timeout=20)
    except httpx.HTTPError as e:
        raise PokedexIndisponible() from e
    if r.status_code == 404:
        raise PokemonInconnu(pokemon_id)
    if r.status_code != 200:
        raise PokedexIndisponible()
    return r.json()


def fetch_profiles(pokemon_ids: list) -> list[dict]:
    """Les profils sont demandés en parallèle, l'ordre de l'équipe est conservé."""
    with ThreadPoolExecutor(max_workers=6) as pool:
        return list(pool.map(_get_profile, pokemon_ids))


def compare(team_a: dict, team_b: dict) -> dict:
    try:
        r = httpx.post(f"{settings.POKEDEX_URL}/teams/compare",
                       json={"teamA": team_a, "teamB": team_b}, timeout=20)
        r.raise_for_status()
    except httpx.HTTPError as e:
        raise PokedexIndisponible() from e
    return r.json()

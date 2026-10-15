"""Donjons et boss final : Équipes vérifie l'équipe et enregistre les victoires,
le Pokédex décide qui peut entrer et calcule le combat."""
from datetime import datetime, timezone

from rest_framework.response import Response

from . import pokedex
from .capture import apply_evolutions, captures, load
from .domain import to_api
from .views import AuthenticatedView, check_playable, error, find_team


def own_playable_team(uid, team_id):
    """L'équipe du dresseur, si elle peut combattre : (équipe, None) ou (None, erreur)."""
    team = find_team(team_id)
    if team is None or team["userId"] != uid:
        return None, error("Équipe introuvable", 404)
    bloque = check_playable(team)
    return (None, bloque) if bloque else (team, None)


def record_win(uid, team, reward_id=None, extra=None):
    """+1 victoire pour chaque membre (par espèce), récompense éventuelle, en une mise à jour."""
    update = {"$inc": {f"victories.{m.get('baseSpecies') or m['name']}": 1 for m in team["members"]}}
    if reward_id is not None:
        update["$addToSet"] = {"unlocked": reward_id}
    if extra:
        update["$set"] = extra
    captures().update_one({"userId": uid}, update)
    return apply_evolutions(uid)[0]


def boss_side(target):
    """Côté B de l'arène : même format que les équipes, une seule « carte » géante."""
    return {"nom": target["name"], "boss": True, "members": [{
        "pokemonId": target["id"], "name": target["name"], "sprite": target["sprite"],
        "artwork": target.get("artwork"), "types": target["types"],
        "isMega": target.get("kind") == "mega" or target.get("isMega", False)}]}


class DungeonsView(AuthenticatedView):
    def get(self, request):
        doc = load(self.uid)
        try:
            state = pokedex.dungeons_state(doc["unlocked"] if doc else [])
        except pokedex.PokedexIndisponible:
            return error("Service Pokédex indisponible", 503)
        return Response({**state, "started": doc is not None,
                         "ultimateDefeated": (doc or {}).get("ultimate")})


class DungeonFightView(AuthenticatedView):
    def post(self, request, dungeon_id):
        team, err = own_playable_team(self.uid, request.data.get("teamId"))
        if err:
            return err
        doc = load(self.uid)
        if doc is None:
            return error("Commence le mode Capture pour accéder aux donjons", 400)
        try:
            result = pokedex.dungeon_fight({"name": team["nom"], **team["summary"]}, dungeon_id, doc["unlocked"])
        except pokedex.PokedexRefus as e:
            return error(str(e), 400)
        except pokedex.PokemonInconnu:
            return error("Donjon inconnu", 404)
        except pokedex.PokedexIndisponible:
            return error("Service Pokédex indisponible", 503)

        dungeon = result["dungeon"]
        won = result["winner"] == "A"
        captured = dungeon["reward"] if won and not dungeon["conquered"] else None
        evolutions = record_win(self.uid, team, captured["id"] if captured else None) if won else []
        result["teams"] = {"A": to_api(team), "B": boss_side(dungeon)}
        return Response({"combat": result, "won": won, "captured": captured, "evolutions": evolutions})


class BossView(AuthenticatedView):
    def post(self, request, team_id):
        """Ton équipe contre le boss final, Éthernatos Infinimax."""
        team, err = own_playable_team(self.uid, team_id)
        if err:
            return err
        try:
            result = pokedex.fight_boss({"name": team["nom"], **team["summary"]})
        except pokedex.PokedexRefus as e:
            return error(str(e), 400)
        except pokedex.PokedexIndisponible:
            return error("Service Pokédex indisponible", 503)
        boss = result["boss"]
        if result["winner"] == "A" and load(self.uid):
            record_win(self.uid, team, extra={"ultimate": {
                "defeatedAt": datetime.now(timezone.utc).isoformat(), "team": team["nom"]}})
        # Même format que le versus : le front réutilise la même arène
        result["teams"] = {"A": to_api(team), "B": boss_side(boss)}
        return Response(result)

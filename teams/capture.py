"""Mode Capture : progression des dresseurs (collection, victoires, run en cours).

Les règles (paliers, rencontres, seuils d'évolution) sont dans le Pokédex ;
ce module stocke la progression et garantit qu'elle ne change que par le serveur :
un dresseur ne peut capturer qu'un Pokémon qu'il vient de battre, ni faire évoluer
un Pokémon qui n'a pas assez de victoires.
"""
from django.conf import settings
from pymongo import ReturnDocument
from rest_framework import status
from rest_framework.response import Response

from . import pokedex
from .db import captures_collection
from .domain import MAX_MEMBERS, check_megas, check_species, snapshot
from .views import AuthenticatedView, error

ROUNDS_PER_RUN = 3


def captures():
    """Collection MongoDB voisine des équipes : un document par dresseur."""
    return captures_collection()


def load(uid):
    return captures().find_one({"userId": uid})


def apply_evolutions(uid):
    """Débloque les évolutions automatiques et met à jour les choix en attente.
    $addToSet garantit qu'un déblocage n'est jamais compté deux fois."""
    doc = load(uid)
    state = pokedex.capture_state(doc["unlocked"], doc.get("victories", {}))
    unlocked_now = [u for u in state["progression"]["unlock"] if u not in doc["unlocked"]]
    update = {"$set": {"choices": state["progression"]["choices"]}}
    if unlocked_now:
        update["$addToSet"] = {"unlocked": {"$each": unlocked_now}}
    captures().update_one({"userId": uid}, update)
    if unlocked_now:  # un déblocage peut en rendre un autre possible (rare), on recalcule l'état
        state = pokedex.capture_state(doc["unlocked"] + unlocked_now, doc.get("victories", {}))
    return unlocked_now, state


def public(doc, state):
    return {
        "starter": doc["starter"],
        "victories": doc.get("victories", {}),
        "run": doc.get("run"),
        "choices": state["progression"]["choices"],
        "progress": state["progression"]["progress"],
        "collection": state["collection"],
        "tiers": state["tiers"],
        # Pour la création d'équipe (silhouettes) et le Pokédex du dresseur
        "unlockedSpecies": state.get("unlockedSpecies", []),
        "unlockedMegas": state.get("unlockedMegas", []),
        "pokedex": state.get("pokedex"),
    }


def run_team(ids, unlocked, tier):
    """Équipe composée au lancement de la run, pour son palier :
    (membres, summary, None) ou (None, None, erreur)."""
    ids = [i for i in ids if i not in (None, "", 0)]
    if not 1 <= len(ids) <= MAX_MEMBERS:
        return None, None, error(f"Une équipe contient entre 1 et {MAX_MEMBERS} Pokémon", 400)
    try:
        analyse = pokedex.capture_analyze(ids, unlocked, tier)
    except pokedex.PokemonInconnu as e:
        return None, None, error(f"Pokémon inconnu : {e}", 400)
    if analyse["forbidden"]:
        return None, None, error(f"Pas encore débloqué : {', '.join(analyse['forbidden'])}", 400)
    if analyse.get("tooStrong"):
        return None, None, error(
            f"Trop fort pour ce palier (2 paliers ou plus au-dessus) : {', '.join(analyse['tooStrong'])}", 400)
    regle = check_species(analyse["members"]) or check_megas(analyse["members"])
    if regle:
        return None, None, error(regle, 400)
    return [snapshot(m) for m in analyse["members"]], analyse["summary"], None


class CaptureView(AuthenticatedView):
    def get(self, request):
        doc = load(self.uid)
        if doc is None:
            return Response({"started": False, "starters": pokedex.capture_starters()})
        if doc.get("run") and "team" not in doc["run"]:
            # run lancée avant que l'équipe soit composée à chaque run : on l'annule
            captures().update_one({"userId": self.uid}, {"$set": {"run": None}})
        _, state = apply_evolutions(self.uid)
        return Response({"started": True, **public(load(self.uid), state)})


class CaptureStartView(AuthenticatedView):
    def post(self, request):
        starter = request.data.get("starter")
        ids = {s["id"] for s in pokedex.capture_starters()}
        if starter not in ids:
            return error("Choisis un des starters proposés", 400)
        if load(self.uid):
            return error("Tu as déjà commencé le mode Capture", 409)
        captures().insert_one({"userId": self.uid, "starter": starter, "unlocked": [starter],
                               "victories": {}, "run": None, "choices": []})
        doc = load(self.uid)
        return Response(public(doc, pokedex.capture_state(doc["unlocked"], {})), status=status.HTTP_201_CREATED)


class CaptureRunView(AuthenticatedView):
    def post(self, request):
        """Démarre une run dans un palier : 3 combats d'affilée, avec une équipe composée
        pour l'occasion et figée jusqu'à la capture ou la défaite."""
        doc = load(self.uid)
        if doc is None:
            return error("Mode Capture non commencé", 404)
        if doc.get("run"):
            return Response(doc["run"])
        tier = request.data.get("tier")
        if not isinstance(tier, int):
            return error("Palier invalide", 400)
        members, summary, err = run_team(request.data.get("pokemonIds", []), doc["unlocked"], tier)
        if err:
            return err
        tirage = pokedex.capture_encounters(tier, doc["unlocked"], [])
        if not tirage["candidates"]:
            return error("Aucun Pokémon dans ce palier", 400)
        # Palier terminé : entraînement (victoires pour les évolutions, pas de capture)
        run = {"tier": tier, "round": 1, "candidates": tirage["candidates"], "defeated": [], "reward": False,
               "training": tirage["training"], "team": members, "summary": summary}
        captures().update_one({"userId": self.uid}, {"$set": {"run": run}})
        return Response(run, status=status.HTTP_201_CREATED)

    def delete(self, request):
        captures().update_one({"userId": self.uid}, {"$set": {"run": None}})
        return Response(status=status.HTTP_204_NO_CONTENT)


class CaptureFightView(AuthenticatedView):
    def post(self, request):
        doc = load(self.uid)
        run = doc and doc.get("run")
        if not run or run["reward"]:
            return error("Aucun combat en cours", 409)
        wild = next((c for c in run["candidates"] if c["id"] == request.data.get("wildId")), None)
        if wild is None:
            return error("Ce Pokémon ne fait pas partie des adversaires proposés", 400)

        team = run["team"]
        result = pokedex.capture_fight({"name": "Ton équipe", **run["summary"]}, wild["id"], len(team))
        won = result["winner"] == "A"

        if won:
            # +1 victoire pour chaque membre engagé (par espèce : une Méga compte pour son espèce)
            inc = {f"victories.{m['baseSpecies']}": 1 for m in team}
            defeated = run["defeated"] + [wild]
            finished = len(defeated) >= ROUNDS_PER_RUN
            training = run.get("training", False)
            candidates = [] if finished else pokedex.capture_encounters(
                run["tier"], doc["unlocked"], [d["id"] for d in defeated])["candidates"]
            if finished and training:
                new_run = None                                # entraînement réussi : pas de capture
            else:
                new_run = {**run, "defeated": defeated, "round": run["round"] + 1,
                           "reward": finished, "candidates": candidates}
                if not finished and not candidates:
                    new_run.update(reward=True, candidates=[])   # palier épuisé : on récompense quand même
            # Condition sur le numéro de manche : un double clic ne compte pas deux fois
            updated = captures().find_one_and_update(
                {"userId": self.uid, "run.round": run["round"]},
                {"$inc": inc, "$set": {"run": new_run}}, return_document=ReturnDocument.AFTER)
            if updated is None:
                return error("Ce combat a déjà été joué", 409)
            unlocked_now, state = apply_evolutions(self.uid)
        else:
            captures().update_one({"userId": self.uid, "run.round": run["round"]}, {"$set": {"run": None}})
            unlocked_now, state = [], pokedex.capture_state(doc["unlocked"], doc.get("victories", {}))

        doc = load(self.uid)
        result["teams"] = {
            "A": {"nom": "Ton équipe", "summary": run["summary"], "members": team},
            "B": {"nom": wild["name"], "sauvage": True, "members": [{**result["wild"], "pokemonId": wild["id"]}]},
        }
        training_done = won and run.get("training", False) and len(run["defeated"]) + 1 >= ROUNDS_PER_RUN
        return Response({"combat": result, "won": won, "evolutions": unlocked_now,
                         "trainingComplete": training_done, **public(doc, state)})


class CaptureRewardView(AuthenticatedView):
    def post(self, request):
        """Après 3 victoires : on choisit lequel des Pokémon battus capturer (son 1er stade)."""
        doc = load(self.uid)
        run = doc and doc.get("run")
        if not run or not run["reward"]:
            return error("Aucune capture disponible", 409)
        beaten = next((d for d in run["defeated"] if d["id"] == request.data.get("pokemonId")), None)
        if beaten is None:
            return error("Tu ne peux capturer qu'un Pokémon battu pendant cette run", 400)
        first = beaten["firstStage"]["id"]
        captures().update_one({"userId": self.uid, "run.reward": True},
                              {"$addToSet": {"unlocked": first}, "$set": {"run": None}})
        _, state = apply_evolutions(self.uid)
        return Response({"captured": beaten["firstStage"], **public(load(self.uid), state)})


class CaptureEvolutionView(AuthenticatedView):
    def post(self, request):
        """Choix d'une branche d'évolution (Évoli...) quand le seuil est atteint."""
        doc = load(self.uid)
        if doc is None:
            return error("Mode Capture non commencé", 404)
        state = pokedex.capture_state(doc["unlocked"], doc.get("victories", {}))
        target = request.data.get("to")
        allowed = {o["id"] for c in state["progression"]["choices"] for o in c["options"]}
        if target not in allowed:
            return error("Cette évolution n'est pas disponible", 400)
        captures().update_one({"userId": self.uid}, {"$addToSet": {"unlocked": target}})
        _, state = apply_evolutions(self.uid)
        return Response(public(load(self.uid), state))

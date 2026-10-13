from bson import ObjectId
from bson.errors import InvalidId
from rest_framework import serializers, status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import APIView

from . import pokedex
from .db import teams_collection
from .domain import MAX_MEMBERS, check_megas, extract_pokemon_ids, snapshot, to_api


class TeamSerializer(serializers.Serializer):
    nom = serializers.CharField(max_length=250)
    typePrincipal = serializers.CharField(max_length=20, required=False, allow_blank=True)
    isPublic = serializers.BooleanField(required=False)


def error(message, code):
    return Response({"error": message}, status=code)


def user_id(request):
    """La gateway a vérifié le JWT et transmis l'id dans X-User-Id."""
    return request.headers.get("X-User-Id")


def find_team(team_id):
    try:
        return teams_collection().find_one({"_id": ObjectId(team_id)})
    except InvalidId:
        return None


def can_see(doc, uid):
    return doc is not None and (doc["userId"] == uid or doc.get("isPublic", False))


def build_members(data):
    """Valide la liste, fait analyser l'équipe par le Pokédex et construit les instantanés.
    Renvoie (membres, summary, None) ou (None, None, Response d'erreur)."""
    ids = extract_pokemon_ids(data)
    if not 1 <= len(ids) <= MAX_MEMBERS:
        return None, None, error(f"Une équipe contient entre 1 et {MAX_MEMBERS} Pokémon", 400)
    try:
        analyse = pokedex.analyze(ids)
    except pokedex.PokemonInconnu as e:
        return None, None, error(f"Pokémon inconnu : {e}", 400)
    except pokedex.PokedexIndisponible:
        return None, None, error("Service Pokédex indisponible", 503)
    regle = check_megas(analyse["members"])
    if regle:
        return None, None, error(regle, 400)
    return [snapshot(p) for p in analyse["members"]], analyse["summary"], None


class NonAuthentifie(APIException):
    status_code = 401
    default_detail = "Non authentifié"


class AuthenticatedView(APIView):
    """Toutes les routes équipes exigent l'en-tête posé par la gateway."""

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self.uid = user_id(request)
        if not self.uid:
            raise NonAuthentifie()


class TeamsView(AuthenticatedView):
    def get(self, request):
        """Mes équipes."""
        docs = teams_collection().find({"userId": self.uid}).sort("_id", -1)
        return Response([to_api(d) for d in docs])

    def post(self, request):
        s = TeamSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        members, summary, err = build_members(request.data)
        if err:
            return err
        doc = {
            "userId": self.uid,
            "nom": s.validated_data["nom"],
            "typePrincipal": s.validated_data.get("typePrincipal", ""),
            "isPublic": s.validated_data.get("isPublic", False),
            "members": members,
            "summary": summary,
        }
        doc["_id"] = teams_collection().insert_one(doc).inserted_id
        return Response(to_api(doc), status=status.HTTP_201_CREATED)


class PublicTeamsView(AuthenticatedView):
    def get(self, request):
        docs = teams_collection().find({"isPublic": True}).sort("_id", -1).limit(50)
        return Response([to_api(d) for d in docs])


class TeamDetailView(AuthenticatedView):
    def get(self, request, team_id):
        doc = find_team(team_id)
        if not can_see(doc, self.uid):
            return error("Équipe introuvable", 404)
        return Response(to_api(doc))

    def put(self, request, team_id):
        doc = find_team(team_id)
        if doc is None or doc["userId"] != self.uid:
            return error("Équipe introuvable", 404)
        s = TeamSerializer(data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        changes = dict(s.validated_data)
        if extract_pokemon_ids(request.data):
            members, summary, err = build_members(request.data)
            if err:
                return err
            changes["members"] = members
            changes["summary"] = summary
        teams_collection().update_one({"_id": doc["_id"]}, {"$set": changes})
        return Response(to_api({**doc, **changes}))

    def delete(self, request, team_id):
        doc = find_team(team_id)
        if doc is None or doc["userId"] != self.uid:  # corrige la faille du monolithe
            return error("Équipe introuvable", 404)
        teams_collection().delete_one({"_id": doc["_id"]})
        return Response(status=status.HTTP_204_NO_CONTENT)


class VersusView(AuthenticatedView):
    def post(self, request, id_a, id_b):
        a, b = find_team(id_a), find_team(id_b)
        if not can_see(a, self.uid) or not can_see(b, self.uid):
            return error("Équipe introuvable", 404)
        try:
            result = pokedex.compare(
                {"name": a["nom"], **a["summary"]},
                {"name": b["nom"], **b["summary"]},
            )
        except pokedex.PokedexIndisponible:
            return error("Service Pokédex indisponible", 503)
        # Le front a besoin des sprites pour afficher l'affrontement
        result["teams"] = {"A": to_api(a), "B": to_api(b)}
        return Response(result)


class HealthView(APIView):
    def get(self, request):
        return Response({"status": "ok"})

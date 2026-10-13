"""Tests contre le vrai MongoDB (base equipes_test), Pokédex simulé."""
from unittest.mock import patch

from django.test import override_settings
from rest_framework.test import APISimpleTestCase

from . import db

PROFILES = {
    6: {"id": 6, "name": "charizard", "baseSpecies": "charizard", "sprite": "6.png", "types": ["fire", "flying"],
        "stats": {}, "statTotal": 534,
        "weaknesses": ["water", "electric", "rock"],
        "resistances": ["fire", "grass", "fighting", "ground", "bug", "steel", "fairy"]},
    9: {"id": 9, "name": "blastoise", "sprite": "9.png", "types": ["water"],
        "stats": {}, "statTotal": 530,
        "weaknesses": ["electric", "grass"], "resistances": ["fire", "water", "ice", "steel"]},
    10034: {"id": 10034, "name": "charizard-mega-x", "baseSpecies": "charizard", "sprite": "10034.png", "types": ["fire", "dragon"],
            "isMega": True, "stats": {}, "statTotal": 634,
            "weaknesses": ["ground", "rock", "dragon"], "resistances": ["fire", "steel", "bug", "electric", "fairy"]},
    10041: {"id": 10041, "name": "gyarados-mega", "sprite": "10041.png", "types": ["water", "dark"],
            "isMega": True, "stats": {}, "statTotal": 640,
            "weaknesses": ["electric", "grass", "fighting", "bug", "fairy"],
            "resistances": ["fire", "water", "ice", "steel", "ghost", "dark", "psychic"]},
    25: {"id": 25, "name": "pikachu", "sprite": "25.png", "types": ["electric"],
         "stats": {}, "statTotal": 320,
         "weaknesses": ["ground"], "resistances": ["electric", "flying", "steel"]},
}


def fake_analyze(ids):
    """Imite POST /teams/analyze du Pokédex (profils + summary)."""
    from .pokedex import PokemonInconnu
    unknown = [i for i in ids if int(i) not in PROFILES]
    if unknown:
        raise PokemonInconnu(unknown[0])
    members = [PROFILES[int(i)] for i in ids]
    weak, resist, offensive = {}, {}, []
    for m in members:
        for t in m["weaknesses"]:
            weak[t] = weak.get(t, 0) + 1
        for t in m["resistances"]:
            resist[t] = resist.get(t, 0) + 1
        offensive += [t for t in m["types"] if t not in offensive]
    summary = {"statTotal": sum(m["statTotal"] for m in members), "weak": weak,
               "resist": resist, "offensiveTypes": offensive}
    return {"members": members, "summary": summary}


@override_settings(MONGO_DB="equipes_test")
@patch("teams.pokedex.analyze", side_effect=fake_analyze)
class EquipesTests(APISimpleTestCase):
    def setUp(self):
        db.teams_collection().delete_many({})

    def as_user(self, uid):
        return {"HTTP_X_USER_ID": str(uid)}

    def create(self, uid=1, nom="Team Feu", **pokes):
        body = {"nom": nom, **(pokes or {"poke1": 6, "poke2": 25})}
        return self.client.post("/teams", body, format="json", **self.as_user(uid))

    def test_sans_en_tete_gateway(self, _):
        self.assertEqual(self.client.get("/teams").status_code, 401)

    def test_creation_instantane_et_summary(self, _):
        r = self.create()
        self.assertEqual(r.status_code, 201)
        t = r.json()
        self.assertEqual([m["name"] for m in t["members"]], ["charizard", "pikachu"])
        self.assertEqual((t["poke1"], t["poke2"], t["poke3"]), (6, 25, None))
        s = t["summary"]
        self.assertEqual(s["statTotal"], 854)
        self.assertEqual(s["weak"]["electric"], 1)      # Dracaufeu
        self.assertEqual(s["resist"]["steel"], 2)       # les deux
        self.assertEqual(s["offensiveTypes"], ["fire", "flying", "electric"])

    def test_creation_invalide(self, _):
        self.assertEqual(self.create(poke1=None).status_code, 400)       # aucun Pokémon
        self.assertEqual(self.create(poke1=99999).status_code, 400)      # inconnu

    def test_un_seul_exemplaire_par_espece(self, _):
        r = self.create(poke1=6, poke2=25, poke3=6)
        self.assertEqual(r.status_code, 400)
        self.assertIn("Un seul exemplaire", r.json()["error"])
        # une Méga compte comme son espèce de base
        self.assertEqual(self.create(poke1=6, poke2=10034).status_code, 400)

    def test_une_seule_mega_par_equipe(self, _):
        r = self.create(poke1=10034, poke2=25)
        self.assertEqual(r.status_code, 201)
        self.assertTrue(r.json()["members"][0]["isMega"])
        r = self.create(poke1=10034, poke2=10041)
        self.assertEqual(r.status_code, 400)
        self.assertIn("Une seule Méga", r.json()["error"])

    def test_liste_uniquement_mes_equipes(self, _):
        self.create(uid=1)
        self.create(uid=2)
        r = self.client.get("/teams", **self.as_user(1))
        self.assertEqual(len(r.json()), 1)

    def test_suppression_par_le_proprietaire_uniquement(self, _):
        tid = self.create(uid=1).json()["idTeam"]
        self.assertEqual(self.client.delete(f"/teams/{tid}", **self.as_user(2)).status_code, 404)
        self.assertEqual(self.client.delete(f"/teams/{tid}", **self.as_user(1)).status_code, 204)
        self.assertEqual(self.client.get(f"/teams/{tid}", **self.as_user(1)).status_code, 404)

    def test_id_invalide(self, _):
        self.assertEqual(self.client.get("/teams/pas-un-id", **self.as_user(1)).status_code, 404)

    def test_modification(self, _):
        tid = self.create().json()["idTeam"]
        r = self.client.put(f"/teams/{tid}", {"nom": "Team Eau", "poke1": 9}, format="json",
                            **self.as_user(1))
        self.assertEqual(r.json()["nom"], "Team Eau")
        self.assertEqual(r.json()["summary"]["statTotal"], 530)

    def test_versus_envoie_les_summaries_au_pokedex(self, _):
        a = self.create(nom="Feu", poke1=6).json()["idTeam"]
        b = self.create(nom="Eau", poke1=9).json()["idTeam"]
        with patch("teams.pokedex.compare", return_value={"winner": "B"}) as compare:
            r = self.client.post(f"/teams/{a}/versus/{b}", **self.as_user(1))
        self.assertEqual(r.status_code, 200)
        team_a, team_b = compare.call_args.args
        self.assertEqual(team_a["name"], "Feu")
        self.assertEqual(team_a["statTotal"], 534)
        self.assertEqual(team_b["offensiveTypes"], ["water"])
        self.assertEqual(r.json()["teams"]["B"]["members"][0]["sprite"], "9.png")

    def test_combat_contre_le_boss(self, _):
        tid = self.create(nom="Eau", poke1=9).json()["idTeam"]
        boss = {"id": 384, "name": "rayquaza-mega", "sprite": "384.png", "artwork": "art.png",
                "types": ["dragon", "flying"], "isMega": True}
        with patch("teams.pokedex.fight_boss", return_value={"winner": "B", "boss": boss}) as fight:
            r = self.client.post(f"/teams/{tid}/boss", **self.as_user(1))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(fight.call_args.args[0]["statTotal"], 530)
        self.assertTrue(r.json()["teams"]["B"]["boss"])
        self.assertEqual(r.json()["teams"]["B"]["members"][0]["artwork"], "art.png")
        # l'équipe d'un autre dresseur ne peut pas être envoyée au combat
        self.assertEqual(self.client.post(f"/teams/{tid}/boss", **self.as_user(2)).status_code, 404)

    def test_versus_equipe_privee_d_un_autre(self, _):
        mine = self.create(uid=1).json()["idTeam"]
        other = self.create(uid=2).json()["idTeam"]
        r = self.client.post(f"/teams/{mine}/versus/{other}", **self.as_user(1))
        self.assertEqual(r.status_code, 404)

    def test_versus_equipe_publique_d_un_autre(self, _):
        mine = self.create(uid=1).json()["idTeam"]
        other = self.client.post("/teams", {"nom": "Pub", "poke1": 9, "isPublic": True},
                                 format="json", **self.as_user(2)).json()["idTeam"]
        with patch("teams.pokedex.compare", return_value={"winner": "A"}):
            r = self.client.post(f"/teams/{mine}/versus/{other}", **self.as_user(1))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(self.client.get("/teams/public", **self.as_user(1)).json()), 1)

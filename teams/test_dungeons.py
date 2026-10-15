"""Donjons et boss final côté Équipes : équipe vérifiée, victoire enregistrée.
Les règles d'entrée et le combat sont simulés (testés dans le Pokédex)."""
from unittest.mock import patch

from django.test import override_settings
from rest_framework.test import APISimpleTestCase

from . import db
from .pokedex import PokedexRefus

MEMBRES = [{"pokemonId": 6, "name": "charizard", "baseSpecies": "charizard", "sprite": "6.png", "types": ["fire"],
            "stats": {}, "statTotal": 534, "weaknesses": [], "resistances": []}]
MEWTWO = {"id": 150, "name": "mewtwo", "kind": "legendary", "statTotal": 680, "types": ["psychic"],
          "sprite": "150.png", "artwork": "art150.png", "requirement": 2040,
          "reward": {"id": 150, "name": "mewtwo"}, "conquered": False}
SCENARIO = {"winner": "A", "refus": None}


def fake_fight(team, dungeon_id, unlocked):
    if SCENARIO["refus"]:
        raise PokedexRefus(SCENARIO["refus"])
    return {"winner": SCENARIO["winner"], "teamA": {}, "teamB": {}, "dungeon": MEWTWO}


def fake_state(unlocked, victories):
    return {"collection": [], "unlockedSpecies": [], "progression": {"unlock": [], "choices": [], "progress": {}},
            "tiers": []}


@override_settings(MONGO_DB="equipes_test")
@patch("teams.pokedex.capture_locked", side_effect=lambda teams: {k: [] for k in teams})
@patch("teams.pokedex.capture_state", side_effect=fake_state)
@patch("teams.pokedex.dungeon_fight", side_effect=fake_fight)
@patch("teams.pokedex.dungeons_state", return_value={"open": True, "dungeons": [MEWTWO]})
class DonjonsTests(APISimpleTestCase):
    def setUp(self):
        db.teams_collection().delete_many({})
        db.captures_collection().delete_many({})
        SCENARIO.update(winner="A", refus=None)
        db.captures_collection().insert_one({"userId": "1", "unlocked": [4, 5, 6], "victories": {}})
        self.team = str(db.teams_collection().insert_one({
            "userId": "1", "nom": "Feu", "members": MEMBRES,
            "summary": {"statTotal": 2100, "weak": {}, "resist": {}, "offensiveTypes": ["fire"]}}).inserted_id)

    def fight(self, uid="1", team=None):
        return self.client.post("/dungeons/150/fight", {"teamId": team or self.team}, format="json",
                                HTTP_X_USER_ID=uid)

    def test_etat_des_donjons(self, *_):
        r = self.client.get("/dungeons", HTTP_X_USER_ID="1").json()
        self.assertTrue(r["open"] and r["started"])
        self.assertIsNone(r["ultimateDefeated"])

    def test_victoire_debloque_et_compte(self, *_):
        r = self.fight().json()
        self.assertTrue(r["won"])
        self.assertEqual(r["captured"]["id"], 150)
        self.assertTrue(r["combat"]["teams"]["B"]["boss"])
        doc = db.captures_collection().find_one({"userId": "1"})
        self.assertIn(150, doc["unlocked"])
        self.assertEqual(doc["victories"], {"charizard": 1})

    def test_defaite_ne_debloque_rien(self, *_):
        SCENARIO["winner"] = "B"
        r = self.fight().json()
        self.assertFalse(r["won"])
        self.assertNotIn(150, db.captures_collection().find_one({"userId": "1"})["unlocked"])

    def test_entree_refusee_par_le_pokedex(self, *_):
        SCENARIO["refus"] = "Équipe trop faible : 2100 / 2040"
        r = self.fight()
        self.assertEqual(r.status_code, 400)
        self.assertIn("trop faible", r.json()["error"])

    def test_equipe_d_un_autre(self, *_):
        self.assertEqual(self.fight(uid="2").status_code, 404)

    def test_boss_final_vaincu_enregistre(self, *_):
        boss = {"id": 10190, "name": "eternatus-eternamax", "sprite": "e.png", "artwork": "a.png",
                "types": ["poison", "dragon"]}
        with patch("teams.pokedex.fight_boss", return_value={"winner": "A", "boss": boss}):
            r = self.client.post(f"/teams/{self.team}/boss", HTTP_X_USER_ID="1")
        self.assertEqual(r.status_code, 200)
        doc = db.captures_collection().find_one({"userId": "1"})
        self.assertEqual(doc["ultimate"]["team"], "Feu")
        with patch("teams.pokedex.fight_boss", side_effect=PokedexRefus("Équipe trop faible")):
            self.assertEqual(self.client.post(f"/teams/{self.team}/boss", HTTP_X_USER_ID="1").status_code, 400)

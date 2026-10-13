"""Mode Capture côté Équipes : stockage de la progression et garde-fous.
Les règles du Pokédex sont simulées (elles sont testées dans le Pokédex)."""
from unittest.mock import patch

from django.test import override_settings
from rest_framework.test import APISimpleTestCase

from . import capture

NAMES = {4: "charmander", 5: "charmeleon", 7: "squirtle", 16: "pidgey", 19: "rattata",
         21: "spearow", 23: "ekans", 25: "pikachu", 133: "eevee", 134: "vaporeon", 135: "jolteon"}
FIRST = {25: 172}  # battre Pikachu donne Pichu
SCENARIO = {"win": True}


def fake_state(unlocked, victories):
    unlock = [5] if victories.get("charmander", 0) >= 3 and 5 not in unlocked else []
    choices = ([{"from": 133, "options": [{"id": 134}, {"id": 135}]}]
               if 133 in unlocked and victories.get("eevee", 0) >= 1 else [])
    return {"collection": [{"id": u} for u in unlocked], "unlockedSpecies": [NAMES.get(u, "") for u in unlocked],
            "progression": {"unlock": unlock, "choices": choices, "progress": {}}, "tiers": []}


def fake_encounters(tier, unlocked, exclude):
    pool = [i for i in (16, 19, 21, 23, 25) if i not in exclude]
    return [{"id": i, "name": NAMES[i], "firstStage": {"id": FIRST.get(i, i), "name": NAMES.get(FIRST.get(i), NAMES[i])}}
            for i in pool[:3]]


def fake_analyze(ids, unlocked):
    members = [{"id": i, "name": NAMES[i], "baseSpecies": NAMES[i], "isMega": False, "types": [],
                "sprite": f"{i}.png", "stats": {}, "statTotal": 300, "weaknesses": [], "resistances": []}
               for i in ids]
    return {"members": members, "summary": {"statTotal": 300, "weak": {}, "resist": {}, "offensiveTypes": []},
            "forbidden": [NAMES[i] for i in ids if i not in unlocked]}


def fake_fight(team, wild_id, size):
    return {"winner": "A" if SCENARIO["win"] else "B", "teamA": {}, "teamB": {},
            "wild": {"id": wild_id, "name": NAMES[wild_id], "sprite": f"{wild_id}.png"}}


@override_settings(MONGO_DB="equipes_test")
@patch("teams.pokedex.capture_starters", return_value=[{"id": 4}, {"id": 7}, {"id": 133}])
@patch("teams.pokedex.capture_state", side_effect=fake_state)
@patch("teams.pokedex.capture_encounters", side_effect=fake_encounters)
@patch("teams.pokedex.capture_analyze", side_effect=fake_analyze)
@patch("teams.pokedex.capture_fight", side_effect=fake_fight)
class CaptureTests(APISimpleTestCase):
    def setUp(self):
        capture.captures().delete_many({})
        SCENARIO["win"] = True

    def call(self, method, path, body=None, uid=1):
        return getattr(self.client, method)(path, body or {}, format="json", HTTP_X_USER_ID=str(uid))

    def start(self, starter=4):
        return self.call("post", "/capture/start", {"starter": starter})

    def lancer(self, team=(4,), tier=6):
        return self.call("post", "/capture/run", {"tier": tier, "pokemonIds": list(team)})

    def test_depart_avec_un_starter(self, *_):
        self.assertFalse(self.call("get", "/capture").json()["started"])
        self.assertEqual(self.start(999).status_code, 400)
        r = self.start(4)
        self.assertEqual(r.status_code, 201)
        self.assertIsNone(r.json()["run"])
        self.assertEqual(self.start(7).status_code, 409)

    def test_run_complete_puis_capture_du_premier_stade(self, *_):
        self.start(4)
        run = self.lancer().json()
        self.assertEqual(len(run["candidates"]), 3)
        self.assertEqual(self.call("post", "/capture/run/fight", {"wildId": 133}).status_code, 400)  # pas proposé

        for _ in range(3):
            wild = self.call("get", "/capture").json()["run"]["candidates"][-1]["id"]
            r = self.call("post", "/capture/run/fight", {"wildId": wild})
            self.assertTrue(r.json()["won"])
        etat = r.json()
        self.assertTrue(etat["run"]["reward"])
        self.assertEqual(etat["victories"], {"charmander": 3})
        self.assertEqual(etat["evolutions"], [5])                       # Reptincel débloqué

        battus = [d["id"] for d in etat["run"]["defeated"]]
        self.assertEqual(self.call("post", "/capture/run/reward", {"pokemonId": 7}).status_code, 400)
        r = self.call("post", "/capture/run/reward", {"pokemonId": 25 if 25 in battus else battus[0]})
        self.assertIsNone(r.json()["run"])
        doc = capture.load("1")
        self.assertIn(r.json()["captured"]["id"], doc["unlocked"])
        if 25 in battus:
            self.assertEqual(r.json()["captured"]["id"], 172)            # Pikachu battu → Pichu

    def test_defaite_termine_la_run(self, *_):
        self.start(4)
        run = self.lancer().json()
        SCENARIO["win"] = False
        r = self.call("post", "/capture/run/fight", {"wildId": run["candidates"][0]["id"]})
        self.assertFalse(r.json()["won"])
        self.assertIsNone(r.json()["run"])
        self.assertEqual(capture.load("1")["victories"], {})

    def test_equipe_de_run_avec_pokemon_non_debloque(self, *_):
        self.start(4)
        r = self.lancer(team=(4, 25))
        self.assertEqual(r.status_code, 400)
        self.assertIn("pikachu", r.json()["error"])
        self.assertEqual(self.lancer(team=()).status_code, 400)

    def test_equipe_composee_a_chaque_run_et_figee(self, *_):
        self.start(4)
        run = self.lancer().json()
        self.assertEqual([m["name"] for m in run["team"]], ["charmander"])
        # relancer pendant une run renvoie la run en cours, sans changer d'équipe
        self.assertEqual(self.lancer(team=(4, 4)).json()["team"], run["team"])
        self.call("delete", "/capture/run")
        self.assertIsNone(self.call("get", "/capture").json()["run"])

    def test_ancienne_run_sans_equipe_annulee(self, *_):
        self.start(4)
        capture.captures().update_one({"userId": "1"}, {"$set": {"run": {"tier": 6, "round": 1}}})
        self.assertIsNone(self.call("get", "/capture").json()["run"])

    def test_choix_evolution(self, *_):
        self.start(133)
        capture.captures().update_one({"userId": "1"}, {"$set": {"victories": {"eevee": 1}}})
        self.assertEqual(len(self.call("get", "/capture").json()["choices"]), 1)
        self.assertEqual(self.call("post", "/capture/evolution", {"to": 5}).status_code, 400)
        r = self.call("post", "/capture/evolution", {"to": 134})
        self.assertIn({"id": 134}, r.json()["collection"])

    def test_progression_propre_a_chaque_dresseur(self, *_):
        self.start(4)
        self.assertFalse(self.call("get", "/capture", uid=2).json()["started"])

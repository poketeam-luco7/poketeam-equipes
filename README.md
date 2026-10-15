# PokéTeam — Équipes

Microservice des **équipes** et de la **progression du mode Capture** (Django + DRF + pymongo +
MongoDB). Il stocke ; le Pokédex calcule (analyse, combats, règles de capture).

| | |
|---|---|
| Stack | Python 3.12, Django 5.1, DRF, pymongo, httpx |
| Base | MongoDB 7 (collections `teams` et `captures`) |
| Port interne | 8002 |
| Appelé par | la gateway |
| Appelle | le Pokédex (`POKEDEX_URL`), directement sur le réseau interne |

## Routes

| Méthode | Route | Rôle |
|---|---|---|
| GET · POST | `/teams` | Mes équipes (avec `locked`) · créer une équipe (Pokémon capturés uniquement) |
| GET · PUT · DELETE | `/teams/{id}` | Lire, modifier, supprimer (propriétaire) |
| GET | `/teams/public` | Équipes publiques |
| POST | `/teams/{a}/versus/{b}` | Affrontement |
| POST | `/teams/{id}/boss` | Combat contre le boss final |
| GET | `/capture` | Progression (collection, Pokédex, paliers, évolutions) |
| POST | `/capture/start` | Choisir son starter |
| POST · DELETE | `/capture/run` | Lancer une run (palier + équipe) ou l'abandonner |
| POST | `/capture/run/fight`, `/capture/run/reward` | Combattre, capturer |
| POST | `/capture/evolution` | Choisir une branche d'évolution |
| GET | `/dungeons` | Donjons visibles et boss final |
| POST | `/dungeons/{id}/fight` | Entrer dans un donjon avec une équipe |

Toutes les routes exigent l'en-tête `X-User-Id`, posé par la gateway après vérification du JWT.

## Variables d'environnement

| Variable | Défaut |
|---|---|
| `MONGO_URL` | `mongodb://localhost:27017` |
| `MONGO_DB` | `equipes` |
| `POKEDEX_URL` | `http://localhost:8000` |
| `DJANGO_SECRET_KEY` | clé de développement |

## Lancer seul

```bash
pip install -r requirements.txt
python manage.py runserver 8002      # nécessite MongoDB et le Pokédex
```

## Tests

```bash
python manage.py test        # 31 tests, contre MongoDB (Pokédex simulé)
```

## Fait partie de PokéTeam

Ce dépôt est un des composants de l'organisation [poketeam-luco7](https://github.com/poketeam-luco7).
Pour lancer l'application complète (gateway, 3 services, 2 bases), voir le dépôt
d'orchestration [`poketeam`](https://github.com/poketeam-luco7/poketeam) : `docker-compose.yml`,
architecture (C4) et décisions d'architecture (ADR).

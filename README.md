# Bonus Stage14h – découvertes, avis et tests de jeux vidéo, en vidéo

Agrégateur des dernières vidéos (hors Shorts) de chaînes YouTube : Loudic, Playmoo, At0mium, Origami.

- `sources.json` : la liste des chaînes (`name` = nom affiché, `handle` = le @pseudo YouTube sans le @, `category` = rubrique).
  Pour ajouter une chaîne, ajoute une ligne. Pour changer le nombre de vidéos d'une chaîne : `"count": 20`.
- `update.py` : récupère les vidéos avec l'API officielle YouTube Data v3 et écrit `data.json`.
  Il lit la clé dans le secret GitHub `YOUTUBE_API_KEY`. Sans clé, il essaie les flux RSS de YouTube, souvent bloqués depuis GitHub.
  Réglages : `PER_SOURCE` (10 vidéos par chaîne), `MAX_TOTAL` (40 vidéos) et `NEWS_PER_SITE` (15 articles par site).
- `.github/workflows/update.yml` : relance `update.py` toutes les 30 minutes.
- `index.html` : la page. `fonds/` : les images de fond tirées au hasard (liste dans `fonds/index.json`).

Les vidéos sont lues avec le lecteur YouTube : les vues et les droits restent aux créateurs.

## Actualités et disposition de l'accueil
- `news_sources.json` : les sites d'actus (Xboxygen, ActuGaming) et leurs flux RSS. Si les flux listés échouent, `update.py` cherche tout seul le flux dans la page d'accueil du site.
- Accueil : la dernière vidéo d'Origami en grand (une seule fois, en haut) + 4 vidéos, puis en alternance 8 actus (2 par ligne) et 8 vidéos.

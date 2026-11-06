# Bonus Stage14h – découvertes, avis et tests de jeux vidéo, en vidéo

Agrégateur des dernières vidéos (hors Shorts) de chaînes YouTube : Loudic, Playmoo, At0mium, Origami.

- `sources.json` : la liste des chaînes (`name` = nom affiché, `handle` = le @pseudo YouTube sans le @, `category` = rubrique).
  Pour ajouter une chaîne, ajoute une ligne. Pour changer le nombre de vidéos d'une chaîne : `"count": 20`.
- `update.py` : récupère les vidéos avec l'API officielle YouTube Data v3 et écrit `data.json`.
  Il lit la clé dans le secret GitHub `YOUTUBE_API_KEY`. Sans clé, il essaie les flux RSS de YouTube, souvent bloqués depuis GitHub.
  Réglages : `PER_SOURCE` (vidéos par chaîne) et `MAX_TOTAL` (total affiché).
- `.github/workflows/update.yml` : relance `update.py` toutes les 30 minutes.
- `index.html` : la page. `fonds/` : les images de fond tirées au hasard (liste dans `fonds/index.json`).

Les vidéos sont lues avec le lecteur YouTube : les vues et les droits restent aux créateurs.

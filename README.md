# Bonus Stage14h – les essais vidéo de jeux, au même endroit

Agrégateur des dernières vidéos (hors Shorts) de chaînes YouTube qui font de l'essai vidéo sur le jeu.

- `sources.json` : la liste des chaînes (`name` = nom affiché, `handle` = le @pseudo YouTube sans le @, `category` = « Essais vidéo » ou « Découverte & avis », qui donne les filtres du haut).
  Pour ajouter une chaîne, ajoute une ligne. Pour changer le nombre de vidéos d'une chaîne : `"count": 20`.
- `update.py` : lit les flux officiels de YouTube (sans clé d'API) et écrit `data.json`.
  Réglages : `PER_SOURCE` (vidéos par chaîne) et `MAX_TOTAL` (total affiché).
- `.github/workflows` : relance `update.py` toutes les 30 minutes.
- `index.html` : la page. `fonds/` : les images de fond tirées au hasard (liste dans `fonds/index.json`).

Les vidéos sont lues avec le lecteur YouTube : les vues et les droits restent aux créateurs.

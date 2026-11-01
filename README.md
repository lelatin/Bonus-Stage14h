# l'hebdo14h

1. Mets ces fichiers à la racine d'un dépôt GitHub (en gardant le dossier `.github`).
2. Settings > Pages : branche `main`, dossier `/ (root)`.
3. Onglet Actions > "Mise à jour des articles" > Run workflow (première remplissage de data.json).
   Ensuite, la mise à jour se fait toute seule toutes les 30 minutes.

## Ajouter un site
Ajoute une ligne dans `sources.json` :
{ "name": "Mon site", "site": "https://exemple.com", "color": "#7C3AED" }
Si le flux n'est pas détecté, ajoute `"feed": "https://exemple.com/rss"`.

## Tester chez toi
python update.py && python -m http.server  → http://localhost:8000

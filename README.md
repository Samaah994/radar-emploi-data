# Radar Emploi — Data Engineer

Pipeline de données qui interroge deux API publiques et gratuites (France Travail et Adzuna), filtre selon des mots-clés définis, élimine les doublons déjà vus, et exporte les nouvelles offres dans un CSV.

## Stack
Python 3 · requests · API Offres d'emploi v2 (France Travail) · API Adzuna

## Comment ça marche
1. Authentification auprès de France Travail (et Adzuna si configuré).
2. Recherche par mots-clés définis dans job_radar.py.
3. Comparaison avec les offres déjà vues (offres_vues.json).
4. Export des nouvelles offres dans nouvelles_offres.csv.
5. Automatisé quotidiennement via GitHub Actions, notification par Issue GitHub.

## Limite 
Automatise la veille (trouver, trier, dédoublonner), et pas encore l'envoi de candidatures.

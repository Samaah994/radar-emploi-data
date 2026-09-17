"""
Radar emploi - France Travail + Adzuna
========================================
Cherche automatiquement les nouvelles offres correspondant aux mots-clés
définis ci-dessous, sur deux sources à API publique et gratuite :
France Travail et Adzuna. Ajoute les nouvelles offres à un fichier CSV,
sans jamais re-signaler une offre déjà vue lors d'une exécution précédente.

Avant de lancer :
    pip install -r requirements.txt
    export FT_CLIENT_ID="votre_client_id"
    export FT_CLIENT_SECRET="votre_client_secret"
    export ADZUNA_APP_ID="votre_app_id"
    export ADZUNA_APP_KEY="votre_app_key"

Puis :
    python job_radar.py
"""

import os
import csv
import json
import time
from datetime import datetime, timedelta

import requests

# --- France Travail ------------------------------------------------------
FT_TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=/partenaire"
FT_SEARCH_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"

# --- Adzuna ----------------------------------------------------------------
ADZUNA_SEARCH_URL = "https://api.adzuna.com/v1/api/jobs/fr/search/1"

# --- À PERSONNALISER SELON TES BESOINS -------------------------------------
MOTS_CLES = [
    "data engineer",
    "data engineer alternance stage",
    "data scientist",
    "data analyst",
    "ML engineer",
    "délégué protection données RGPD",
    "chargé conformité RGPD junior",
]

# Modifié : chaîne séparée par des virgules au lieu d'un tuple (ex: "59,75" ou "59" ou None)
DEPARTEMENT_FT = "59,75"

LOCALISATION_ADZUNA = ""  # ex: "Lille" — vide pour toute la France
RESULTATS_PAR_RECHERCHE = 20
JOURS_MAX = 7  # ignore les offres publiées il y a plus de X jours

FICHIER_SUIVI = "offres_vues.json"
FICHIER_RESULTATS = "nouvelles_offres.csv"
# -----------------------------------------------------------------------------


def get_ft_token(client_id, client_secret):
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "api_offresdemploiv2 o2dsoffre",
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    resp = requests.post(FT_TOKEN_URL, data=data, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.json()["access_token"]


def chercher_france_travail(token, mot_cle):
    """Retourne une liste d'offres normalisées depuis France Travail."""
    headers = {"Authorization": f"Bearer {token}"}
    params = {"motsCles": mot_cle}
    
    if DEPARTEMENT_FT:
        params["departement"] = DEPARTEMENT_FT

    date_min = datetime.utcnow() - timedelta(days=JOURS_MAX)
    params["minCreationDate"] = date_min.strftime("%Y-%m-%dT%H:%M:%SZ")

    resp = requests.get(FT_SEARCH_URL, headers=headers, params=params, timeout=15)
    if resp.status_code == 204:
        return []
    resp.raise_for_status()
    
    offres = resp.json().get("resultats", [])
    return [
        {
            "id": f"ft:{o.get('id')}",
            "source": "France Travail",
            "intitule": o.get("intitule", ""),
            "entreprise": o.get("entreprise", {}).get("nom", "Non précisé"),
            "lieu": o.get("lieuTravail", {}).get("libelle", ""),
            "type_contrat": o.get("typeContratLibelle", ""),
            "lien": o.get("origineOffre", {}).get("urlOrigine", ""),
        }
        for o in offres
    ]


def chercher_adzuna(app_id, app_key, mot_cle):
    """Retourne une liste d'offres normalisées depuis Adzuna."""
    params = {
        "app_id": app_id,
        "app_key": app_key,
        "what": mot_cle,
        "results_per_page": RESULTATS_PAR_RECHERCHE,
        "content-type": "application/json",
        "max_days_old": JOURS_MAX,
    }
    if LOCALISATION_ADZUNA:
        params["where"] = LOCALISATION_ADZUNA
        
    resp = requests.get(ADZUNA_SEARCH_URL, params=params, timeout=15)
    resp.raise_for_status()
    
    offres = resp.json().get("results", [])
    return [
        {
            "id": f"az:{o.get('id')}",
            "source": "Adzuna",
            "intitule": o.get("title", ""),
            "entreprise": o.get("company", {}).get("display_name", "Non précisé"),
            "lieu": o.get("location", {}).get("display_name", ""),
            "type_contrat": o.get("contract_type", ""),
            "lien": o.get("redirect_url", ""),
        }
        for o in offres
    ]


def charger_offres_vues():
    if os.path.exists(FICHIER_SUIVI):
        with open(FICHIER_SUIVI, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def sauver_offres_vues(ids):
    with open(FICHIER_SUIVI, "w", encoding="utf-8") as f:
        json.dump(sorted(ids), f)


def ecrire_dernier_run(nouvelles):
    """Résumé markdown des offres trouvées lors de cette exécution."""
    with open("dernier_run.md", "w", encoding="utf-8") as f:
        if not nouvelles:
            f.write("Aucune nouvelle offre trouvée lors de cet exécution.\n")
            return
        f.write(f"## {len(nouvelles)} nouvelle(s) offre(s) trouvée(s)\n\n")
        for offre in nouvelles:
            f.write(
                f"- **[{offre['source']}] {offre['intitule']}** — "
                f"{offre['entreprise']} ({offre['lieu']})\n"
                f"  <{offre['lien']}>\n\n"
            )


def main():
    ft_id = os.environ.get("FT_CLIENT_ID")
    ft_secret = os.environ.get("FT_CLIENT_SECRET")
    az_id = os.environ.get("ADZUNA_APP_ID")
    az_key = os.environ.get("ADZUNA_APP_KEY")

    if not ft_id or not ft_secret:
        raise SystemExit("Il manque FT_CLIENT_ID / FT_CLIENT_SECRET dans les variables d'environnement.")
    if not az_id or not az_key:
        print(" ADZUNA_APP_ID / ADZUNA_APP_KEY absents : Adzuna sera ignoré cette fois.")

    offres_vues = charger_offres_vues()
    nouvelles = []
    token = get_ft_token(ft_id, ft_secret)

    for mot_cle in MOTS_CLES:
        # Recherche France Travail
        try:
            for offre in chercher_france_travail(token, mot_cle):
                if offre["id"] not in offres_vues:
                    nouvelles.append(offre)
                    offres_vues.add(offre["id"])
        except requests.RequestException as e:
            print(f" Erreur lors de la recherche FT pour '{mot_cle}': {e}")

        time.sleep(0.15)

        # Recherche Adzuna
        if az_id and az_key:
            try:
                for offre in chercher_adzuna(az_id, az_key, mot_cle):
                    if offre["id"] not in offres_vues:
                        nouvelles.append(offre)
                        offres_vues.add(offre["id"])
            except requests.RequestException as e:
                print(f" Erreur lors de la recherche Adzuna pour '{mot_cle}': {e}")

            time.sleep(0.15)

    if nouvelles:
        fichier_existe = os.path.exists(FICHIER_RESULTATS)
        with open(FICHIER_RESULTATS, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not fichier_existe:
                writer.writerow(
                    ["date_detectee", "source", "intitule", "entreprise", "lieu", "type_contrat", "lien"]
                )
            for offre in nouvelles:
                writer.writerow(
                    [
                        datetime.now().strftime("%Y-%m-%d"),
                        offre["source"],
                        offre["intitule"],
                        offre["entreprise"],
                        offre["lieu"],
                        offre["type_contrat"],
                        offre["lien"],
                    ]
                )
        print(f" {len(nouvelles)} nouvelle(s) offre(s) ajoutée(s) à {FICHIER_RESULTATS}")
    else:
        print("Aucune nouvelle offre cette fois-ci.")

    ecrire_dernier_run(nouvelles)
    sauver_offres_vues(offres_vues)


if __name__ == "__main__":
    main()

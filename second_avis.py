"""Second avis : un agent qui vérifie si une demande d'investissement colle au profil de l'investisseur.

Datathon PolyFinances 2026, défi AlphaForge AI. SIMULATION UNIQUEMENT : aucune transaction,
aucun conseil financier personnalisé. Les profils et portefeuilles sont fictifs.

Principe :
- Python calcule tous les chiffres (fonctions déterministes ci-dessous, les « outils »).
- Le modèle Claude sur Amazon Bedrock choisit les outils, relie les résultats et explique.
- Un contrôle de gouvernance (Python) vérifie que chaque chiffre de l'avis vient bien d'un appel d'outil
  et qu'une alternative proposée a été vérifiée ; sinon l'avis est renvoyé au modèle pour correction.
- Chaque exécution laisse une trace JSON (outils appelés, entrées, sorties, durée, identifiants de requête Bedrock).

Usage dans un notebook :
    from second_avis import SecondAvis, afficher
    sa = SecondAvis(".")                      # dossier qui contient les CSV du jeu de départ
    r = sa.demander("robert", "Tesla est partout aux nouvelles, je veux y mettre 25 % de mon épargne.")
    afficher(r)
"""

from __future__ import annotations

import html
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

MODELE = "global.anthropic.claude-sonnet-5"
REGION = "us-east-1"
SEMAINES_PAR_AN = 52

# ---------------------------------------------------------------------------
# 1. Personas : faits de l'énoncé + HYPOTHÈSES DE L'ÉQUIPE (portefeuille actuel fictif et seuils)
#    Les seuils sont des choix de l'équipe, pas des règles du concours : modifiez-les ici.
# ---------------------------------------------------------------------------

PERSONAS = {
    "amira": {
        "nom": "Amira", "age": 26, "situation": "Ingénieure logicielle, célibataire, sans enfant",
        "experience": "intermédiaire", "profil_risque": "élevé", "horizon": "15 ans ou plus",
        "objectif": "Faire croître son capital à long terme",
        "preferences": [
            "Très intéressée par l'IA, les technologies émergentes et les entreprises en forte croissance",
            "Accepte une volatilité importante, intéressée par les cryptoactifs",
            "Veut garder une certaine diversification et éviter de miser exclusivement sur la technologie",
        ],
        "test_central": "Un profil offensif n'autorise pas une concentration ou un risque sans limites.",
        "portefeuille_actuel": {"QQQ": 25, "SPY": 20, "XIU.TO": 15, "NVDA": 8, "SHOP.TO": 7, "CNR.TO": 7,
                                "CSU.TO": 5, "BTC-USD": 5, "GLD": 5, "ETH-USD": 3},
        "regles": {"poids_max_titre": 15, "crypto_max": 10, "tech_max": 50, "lignes_min": 6, "perte_max": -45},
    },
    "mateo": {
        "nom": "Mateo", "age": 41, "situation": "Gestionnaire des opérations, en couple, deux enfants",
        "experience": "intermédiaire", "profil_risque": "modéré", "horizon": "8 à 12 ans",
        "objectif": "Croissance équilibrée à moyen et long terme",
        "preferences": [
            "Grande importance des facteurs ESG",
            "Veut éviter les entreprises liées à des controverses environnementales ou sociales importantes",
            "Ouvert aux technologies émergentes si elles respectent son profil de risque",
            "Peu intéressé par les placements hautement spéculatifs",
        ],
        "test_central": "Intégrer des préférences non financières avec des preuves, pas seulement rendement et risque.",
        "portefeuille_actuel": {"ESGV": 30, "XBB.TO": 25, "XIU.TO": 15, "AGG": 10, "FTS.TO": 5, "CNR.TO": 5,
                                "MSFT": 5, "ZST.TO": 5},
        "regles": {"poids_max_titre": 10, "crypto_max": 0, "defensif_min": 30, "volatilite_max": 12,
                   "perte_max": -20, "esg": True},
    },
    "robert": {
        "nom": "Robert", "age": 59, "situation": "Professionnel de la santé, marié, enfants adultes, retraite prochaine",
        "experience": "avancée", "profil_risque": "faible à modéré", "horizon": "3 à 5 ans",
        "objectif": "Préserver son capital tout en gardant un potentiel de croissance",
        "preferences": [
            "Préfère les entreprises établies et les modèles d'affaires qu'il comprend",
            "Importance de la stabilité et de la qualité, peu intéressé par les cryptoactifs",
            "Suit activement les marchés, peut être tenté par une entreprise très médiatisée",
        ],
        "test_central": "Détecter une contradiction entre une demande ponctuelle et ses objectifs, ne pas acquiescer automatiquement.",
        "portefeuille_actuel": {"XBB.TO": 30, "XIU.TO": 20, "ZST.TO": 15, "SPY": 15, "JNJ": 5, "PG": 5,
                                "RY.TO": 5, "GLD": 5},
        "regles": {"poids_max_titre": 10, "crypto_max": 0, "titre_volatil_max": 5, "defensif_min": 40,
                   "volatilite_max": 10, "perte_max": -15},
    },
}

DESCRIPTION_REGLES = {
    "poids_max_titre": "Poids maximal d'un titre individuel ou d'un cryptoactif (les FNB, déjà diversifiés, sont exemptés)",
    "crypto_max": "Part maximale des cryptoactifs",
    "tech_max": "Part maximale de la technologie (secteurs Information Technology et Communication Services, et QQQ compté entièrement)",
    "lignes_min": "Nombre minimal de positions, pour garder une diversification",
    "defensif_min": "Part minimale des FNB obligataires (XBB.TO, ZST.TO, AGG, TLT)",
    "volatilite_max": "Volatilité annualisée maximale du portefeuille (historique, hebdomadaire)",
    "perte_max": "Pire baisse historique tolérée du portefeuille (perte maximale du sommet au creux)",
    "titre_volatil_max": "Poids maximal d'un titre très volatil (volatilité historique supérieure à 40 %)",
    "esg": "Aucune position avec une controverse documentée dans le fichier de preuves ESG",
}

NOMS_COURTS = {"poids_max_titre": "poids d'un titre", "crypto_max": "crypto", "tech_max": "techno", "lignes_min": "diversification",
               "defensif_min": "part obligataire", "volatilite_max": "volatilité", "perte_max": "pire baisse",
               "titre_volatil_max": "titre très volatil", "esg": "ESG"}

NOMS_OUTILS = {"poids_maximal_compatible": "recherche du poids maximal compatible", "profil_investisseur": "lecture du profil", "lister_actifs": "liste des actifs disponibles",
               "indicateurs_actif": "indicateurs historiques", "simuler_modification": "simulation avant/après",
               "evaluer_portefeuille": "vérification d'un portefeuille", "preuves_esg": "recherche de preuves ESG"}

SECTEURS_TECH = {"Information Technology", "Communication Services"}
FNB_TECH = {"QQQ"}
SEUIL_TITRE_VOLATIL = 40.0

# Correction documentée : Yahoo enregistre un « fractionnement » de 1,021 pour CNQ.TO le 2022-08-22, le jour d'une
# distribution de 0,75 $ déjà comptée comme dividende. La clôture ajustée gagne +2,8 % ce jour-là alors que clôture +
# dividende donnent environ +0,6 % : la distribution semble comptée deux fois. On retire le facteur 1,021 avant cette date.
# À confirmer auprès des relations investisseurs de CNQ.
CORRECTIONS = [{"symbole": "CNQ.TO", "avant": "2022-08-22", "facteur": 1.021,
                "raison": "Faux fractionnement de 1,021 le même jour qu'une distribution déjà comptée comme dividende"}]

SOURCES = {
    "prix": "prices_daily.csv : Yahoo Finance via yfinance, extrait le 2026-11-13, colonne adj_close (ajustée dividendes et fractionnements)",
    "change": "fx_usdcad_daily.csv : Banque du Canada, série FXUSDCAD (CAD pour 1 USD), extrait le 2026-11-13",
    "univers": "assets_universe.csv : 31 actifs choisis par les organisateurs, secteurs simplifiés (noms GICS)",
    "esg": "esg_preuves.csv : preuves ESG ajoutées à la main par l'équipe, chacune avec sa source et sa date",
    "profils": "Personas de l'énoncé officiel ; portefeuilles actuels et seuils = hypothèses de l'équipe",
}

METHODE = ("Prix convertis en CAD (USD x taux Banque du Canada du jour, ou dernier taux connu, jamais un taux futur), "
           "prix de fin de semaine (vendredi ou dernier prix connu), rendements hebdomadaires, annualisation sur 52 semaines, "
           "portefeuille rééquilibré chaque semaine aux poids indiqués, sans frais ni impôts.")

COLONNES_ESG = ["symbole", "constat", "type", "source", "url", "date_publication"]


# ---------------------------------------------------------------------------
# 2. Données : chargement, conversion en CAD, contrôles
# ---------------------------------------------------------------------------

class Donnees:
    def __init__(self, dossier=".", corriger=True):
        d = Path(dossier)
        self.dossier = d
        self.univers = pd.read_csv(d / "assets_universe.csv").set_index("ticker")
        self.prix = pd.read_csv(d / "prices_daily.csv", parse_dates=["date"])
        self.fx = pd.read_csv(d / "fx_usdcad_daily.csv", parse_dates=["date"]).set_index("date")["usdcad"]
        self.corrections_appliquees = []

        ajuste = self.prix.pivot(index="date", columns="ticker", values="adj_close").sort_index()
        if corriger:
            for c in CORRECTIONS:
                if c["symbole"] in ajuste.columns:
                    masque = ajuste.index < pd.Timestamp(c["avant"])
                    ajuste.loc[masque, c["symbole"]] *= c["facteur"]
                    self.corrections_appliquees.append(c)

        # Calendrier civil + report du dernier prix connu (jamais de valeur future)
        calendrier = pd.date_range(ajuste.index.min(), ajuste.index.max(), freq="D")
        quotidien = ajuste.reindex(calendrier).ffill()
        taux = self.fx.reindex(calendrier).ffill()
        for t in quotidien.columns:
            if self.univers.loc[t, "currency"] == "USD":
                quotidien[t] = quotidien[t] * taux
        self.prix_cad_hebdo = quotidien.resample("W-FRI").last()
        self.rendements = self.prix_cad_hebdo.pct_change().iloc[1:]
        self.debut = self.rendements.index.min()
        self.fin = self.rendements.index.max()
        self.dernier_prix = ajuste.index.max()

    def periode(self):
        return (f"semaines du {self.debut:%Y-%m-%d} au {self.fin:%Y-%m-%d} ({len(self.rendements)} semaines, "
                f"dernier prix le {self.dernier_prix:%Y-%m-%d})")

    def controles(self):
        p = self.prix
        lignes = [
            ("Lignes de prix", f"{len(p)} lignes, {p['ticker'].nunique()} actifs", True),
            ("Doublons (date, symbole)", f"{int(p.duplicated(['date', 'ticker']).sum())}", not p.duplicated(["date", "ticker"]).any()),
            ("Clôtures ajustées positives", "toutes > 0" if (p["adj_close"] > 0).all() else "valeurs nulles ou négatives",
             bool((p["adj_close"] > 0).all())),
        ]
        brut = p[p["ticker"] == "CNQ.TO"].set_index("date").sort_index()
        if pd.Timestamp("2022-08-22") in brut.index:
            i = brut.index.get_loc(pd.Timestamp("2022-08-22"))
            avant, apres = brut.iloc[i - 1], brut.iloc[i]
            saut_ajuste = apres["adj_close"] / avant["adj_close"] - 1
            saut_reel = (apres["close"] + 0.75) / (avant["close"] * 1.021) - 1
            etat = "corrigé" if self.corrections_appliquees else "NON corrigé"
            lignes.append(("CNQ.TO le 2022-08-22",
                           f"clôture ajustée {saut_ajuste:+.1%} contre clôture + dividende {saut_reel:+.1%} : "
                           f"distribution probablement comptée deux fois ({etat})", bool(self.corrections_appliquees)))
        zst = p[(p["ticker"] == "ZST.TO") & (p["volume"] == 0)]
        lignes.append(("Volumes nuls", f"{len(zst)} ligne(s) pour ZST.TO ({', '.join(zst['date'].dt.strftime('%Y-%m-%d'))}) : prix gardé, signalé", True))
        jours_sans_fx = len(pd.date_range(self.fx.index.min(), self.fx.index.max(), freq="B").difference(self.fx.index))
        lignes.append(("Taux de change", f"{jours_sans_fx} jours ouvrables sans taux (fériés canadiens) : dernier taux connu reporté", True))
        crypto = p[p["ticker"] == "BTC-USD"]["date"].nunique()
        action = p[p["ticker"] == "SPY"]["date"].nunique()
        lignes.append(("Calendriers", f"crypto {crypto} jours contre {action} pour SPY : alignement sur la fin de semaine", True))
        return pd.DataFrame(lignes, columns=["controle", "resultat", "ok"])


# ---------------------------------------------------------------------------
# 3. Calculs déterministes
# ---------------------------------------------------------------------------

def _pct(x, n=1):
    return None if x is None or pd.isna(x) else round(float(x) * 100, n)


def _serie_portefeuille(donnees, poids):
    w = pd.Series(poids, dtype=float) / 100.0
    r = donnees.rendements[w.index]
    return (r * w).sum(axis=1)


def _mesures_serie(r):
    valeur = (1 + r).cumprod()
    sommet = valeur.cummax()
    baisse = valeur / sommet - 1
    creux = baisse.idxmin()
    debut_baisse = valeur.loc[:creux].idxmax()
    niveau = valeur.loc[debut_baisse]
    apres = valeur.loc[creux:]
    retour = apres[apres >= niveau]
    annees = len(r) / SEMAINES_PAR_AN
    pires = r.nsmallest(max(1, int(round(len(r) * 0.05))))
    return {
        "rendement_annualise_pct": _pct(valeur.iloc[-1] ** (1 / annees) - 1),
        "volatilite_annualisee_pct": _pct(r.std() * np.sqrt(SEMAINES_PAR_AN)),
        "perte_maximale_pct": _pct(baisse.min()),
        "perte_maximale_periode": f"{debut_baisse:%Y-%m-%d} au {creux:%Y-%m-%d}",
        "recuperation_semaines": int((retour.index[0] - creux).days // 7) if len(retour) else None,
        "recuperation_note": None if len(retour) else "sommet précédent jamais retrouvé avant la fin des données",
        "rendement_2022_pct": _pct((1 + r.loc["2022"]).prod() - 1),
        "perte_moyenne_5pct_pires_semaines_pct": _pct(pires.mean()),
    }


def _contributions_risque(rendements, poids):
    """Part de la variance du portefeuille apportée par chaque position (contribution au risque, en %)."""
    w = pd.Series(poids, dtype=float) / 100.0
    cov = rendements[w.index].cov()
    var = float(w @ cov @ w)
    if var <= 0:
        return {}
    contrib = w * (cov @ w) / var
    return {t: round(float(v) * 100, 1) for t, v in contrib.sort_values(ascending=False).items()}


class Outils:
    """Les fonctions que l'agent peut appeler. Toutes déterministes et vérifiables."""

    def __init__(self, donnees: Donnees, dossier="."):
        self.d = donnees
        chemin = Path(dossier) / "esg_preuves.csv"
        if not chemin.exists():
            pd.DataFrame(columns=COLONNES_ESG).to_csv(chemin, index=False)
        self.esg = pd.read_csv(chemin).fillna("")
        self._vol_titres = {t: _mesures_serie(self.d.rendements[t])["volatilite_annualisee_pct"]
                            for t in self.d.rendements.columns}

    # -- utilitaires -------------------------------------------------------
    def _verifier_symboles(self, symboles):
        inconnus = [s for s in symboles if s not in self.d.univers.index]
        if inconnus:
            return {"erreur": f"Symbole(s) hors de l'univers de données : {', '.join(inconnus)}. "
                              "Aucune donnée de prix disponible, impossible de calculer quoi que ce soit pour eux.",
                    "symboles_disponibles": list(self.d.univers.index)}
        return None

    def _normaliser(self, poids):
        poids = {k: float(v) for k, v in poids.items() if float(v) > 0}
        total = sum(poids.values())
        note = None
        if abs(total - 100) > 0.5:
            note = f"Poids reçus totalisant {total:.1f} % : ramenés à 100 %."
        return {k: round(v * 100 / total, 2) for k, v in poids.items()}, note

    def composition(self, poids):
        u = self.d.univers
        par_classe = {}
        for t, w in poids.items():
            par_classe[u.loc[t, "asset_class"]] = par_classe.get(u.loc[t, "asset_class"], 0) + w
        titres = {t: w for t, w in poids.items() if u.loc[t, "asset_class"] in ("equity", "crypto")}
        plus_gros = max(titres.items(), key=lambda x: x[1]) if titres else (None, 0)
        tech = sum(w for t, w in poids.items() if u.loc[t, "sector"] in SECTEURS_TECH or t in FNB_TECH)
        volatils = {t: w for t, w in titres.items() if self._vol_titres[t] > SEUIL_TITRE_VOLATIL}
        return {
            "nombre_positions": len(poids),
            "plus_gros_titre": {"symbole": plus_gros[0], "poids_pct": round(plus_gros[1], 1)},
            "part_crypto_pct": round(par_classe.get("crypto", 0), 1),
            "part_tech_pct": round(tech, 1),
            "part_obligations_pct": round(par_classe.get("etf_bond", 0), 1),
            "part_actions_pct": round(par_classe.get("equity", 0) + par_classe.get("etf_equity", 0), 1),
            "part_or_pct": round(par_classe.get("etf_commodity", 0), 1),
            "titres_tres_volatils": {t: round(w, 1) for t, w in volatils.items()},
        }

    def contraintes(self, persona, poids, mesures, compo, regles=None):
        regles = regles or PERSONAS[persona]["regles"]
        resultats = []

        def ajouter(cle, valeur, seuil, respecte, detail=None):
            ligne = {"regle": cle, "valeur": valeur, "seuil": seuil, "respectee": bool(respecte)}
            if detail:
                ligne["detail"] = detail
            resultats.append(ligne)

        if "poids_max_titre" in regles:
            v = compo["plus_gros_titre"]["poids_pct"]
            ajouter("poids_max_titre", v, regles["poids_max_titre"], v <= regles["poids_max_titre"] + 1e-9,
                    compo["plus_gros_titre"]["symbole"])
        if "crypto_max" in regles:
            v = compo["part_crypto_pct"]
            ajouter("crypto_max", v, regles["crypto_max"], v <= regles["crypto_max"] + 1e-9)
        if "tech_max" in regles:
            v = compo["part_tech_pct"]
            ajouter("tech_max", v, regles["tech_max"], v <= regles["tech_max"] + 1e-9)
        if "lignes_min" in regles:
            v = compo["nombre_positions"]
            ajouter("lignes_min", v, regles["lignes_min"], v >= regles["lignes_min"])
        if "defensif_min" in regles:
            v = compo["part_obligations_pct"]
            ajouter("defensif_min", v, regles["defensif_min"], v >= regles["defensif_min"] - 1e-9)
        if "volatilite_max" in regles:
            v = mesures["volatilite_annualisee_pct"]
            ajouter("volatilite_max", v, regles["volatilite_max"], v <= regles["volatilite_max"])
        if "perte_max" in regles:
            v = mesures["perte_maximale_pct"]
            ajouter("perte_max", v, regles["perte_max"], v >= regles["perte_max"])
        if "titre_volatil_max" in regles:
            volatils = compo["titres_tres_volatils"]
            v = max(volatils.values()) if volatils else 0
            ajouter("titre_volatil_max", v, regles["titre_volatil_max"], v <= regles["titre_volatil_max"] + 1e-9,
                    ", ".join(volatils) or None)
        if regles.get("esg"):
            controverses = self.esg[(self.esg["symbole"].isin(poids)) & (self.esg["type"] == "controverse")]
            touches = sorted(controverses["symbole"].unique())
            energie = [t for t in poids if self.d.univers.loc[t, "sector"] == "Energy" and t not in touches]
            detail = None
            if energie:
                detail = (f"Secteur énergie sans preuve documentée : {', '.join(energie)}. "
                          "Le secteur seul ne prouve pas une controverse : à vérifier avec des sources.")
            ajouter("esg", ", ".join(touches) or "aucune controverse documentée", "aucune", not touches, detail)
        return {"statut": "conforme" if all(r["respectee"] for r in resultats) else "non conforme",
                "nombre_ecarts": sum(not r["respectee"] for r in resultats), "regles": resultats}

    def _analyse(self, persona, poids, complet=True):
        mesures = _mesures_serie(_serie_portefeuille(self.d, poids))
        compo = self.composition(poids)
        sortie = {"mesures": mesures, "composition": compo, "contraintes": self.contraintes(persona, poids, mesures, compo)}
        if complet:
            contrib = _contributions_risque(self.d.rendements, poids)
            sortie["part_du_risque_pct"] = dict(list(contrib.items())[:3])
        return sortie

    # -- outils exposés au modèle ------------------------------------------
    def profil_investisseur(self, persona):
        if persona not in PERSONAS:
            return {"erreur": f"Persona inconnu. Choix : {', '.join(PERSONAS)}"}
        p = PERSONAS[persona]
        return {
            "faits_de_l_enonce": {k: p[k] for k in ("nom", "age", "situation", "experience", "profil_risque",
                                                    "horizon", "objectif", "preferences", "test_central")},
            "hypotheses_de_l_equipe": {
                "portefeuille_actuel_fictif_pct": p["portefeuille_actuel"],
                "regles": [{"regle": k, "seuil": v, "description": DESCRIPTION_REGLES[k]} for k, v in p["regles"].items()],
            },
            "source": SOURCES["profils"],
            "methode_des_calculs": METHODE,
            "sources_des_donnees": [SOURCES["prix"], SOURCES["change"]],
            "avertissement": "Indicateurs historiques : ils ne prédisent pas les rendements futurs.",
        }

    def lister_actifs(self, classe=None):
        u = self.d.univers.reset_index()
        if classe:
            u = u[u["asset_class"] == classe]
        return {"actifs": [f"{x.ticker} | {x.name} | {x.asset_class} | {x.currency} | {x.sector}" for x in u.itertuples()],
                "classes": sorted(self.d.univers["asset_class"].unique()), "source": SOURCES["univers"]}

    def indicateurs_actif(self, symbole):
        erreur = self._verifier_symboles([symbole])
        if erreur:
            return erreur
        u = self.d.univers.loc[symbole]
        return {"symbole": symbole, "nom": u["name"], "classe": u["asset_class"], "secteur": u["sector"],
                "devise_de_cotation": u["currency"], "devise_d_analyse": "CAD",
                **_mesures_serie(self.d.rendements[symbole]),
                "periode": self.d.periode()}

    def simuler_modification(self, persona, symbole, poids_cible_pct):
        if persona not in PERSONAS:
            return {"erreur": f"Persona inconnu. Choix : {', '.join(PERSONAS)}"}
        erreur = self._verifier_symboles([symbole])
        if erreur:
            return erreur
        x = float(poids_cible_pct)
        if not 0 <= x <= 100:
            return {"erreur": "poids_cible_pct doit être entre 0 et 100."}
        avant = dict(PERSONAS[persona]["portefeuille_actuel"])
        reste = {t: w for t, w in avant.items() if t != symbole}
        total = sum(reste.values())
        apres = {t: round(w * (100 - x) / total, 2) for t, w in reste.items()}
        if x > 0:
            apres[symbole] = round(x, 2)
        return {"persona": persona, "modification": f"{symbole} porté à {x:.1f} % ; les autres positions réduites proportionnellement",
                "avant": {"poids_pct": avant, **self._analyse(persona, avant)},
                "apres": {"poids_pct": apres, **self._analyse(persona, apres)},
                "periode": self.d.periode()}

    def poids_maximal_compatible(self, persona, symbole):
        """Plus grand poids de l'actif (pas de 0,5 point) qui garde le portefeuille actuel conforme, et la règle qui bloque au-delà."""
        if persona not in PERSONAS:
            return {"erreur": f"Persona inconnu. Choix : {', '.join(PERSONAS)}"}
        erreur = self._verifier_symboles([symbole])
        if erreur:
            return erreur
        avant = dict(PERSONAS[persona]["portefeuille_actuel"])
        reste = {t: w for t, w in avant.items() if t != symbole}
        total = sum(reste.values())

        def essai(x):
            poids = {t: w * (100 - x) / total for t, w in reste.items()}
            if x > 0:
                poids[symbole] = x
            return self._analyse(persona, poids, complet=False)["contraintes"]

        if essai(0)["statut"] != "conforme":
            return {"symbole": symbole, "poids_maximal_pct": None,
                    "message": "Le portefeuille actuel sans cet actif ne respecte déjà pas toutes les règles."}
        meilleur, bloquant = 0.0, None
        x = 0.5
        while x <= 100:
            c = essai(x)
            if c["statut"] != "conforme":
                bloquant = [r["regle"] for r in c["regles"] if not r["respectee"]]
                break
            meilleur = x
            x += 0.5
        return {"symbole": symbole, "poids_maximal_pct": meilleur,
                "regles_qui_bloquent_au_dela": bloquant,
                "methode": "Poids testés de 0,5 en 0,5 point, autres positions réduites proportionnellement."}

    def evaluer_portefeuille(self, persona, positions):
        if persona not in PERSONAS:
            return {"erreur": f"Persona inconnu. Choix : {', '.join(PERSONAS)}"}
        poids = {p["symbole"]: p["poids_pct"] for p in positions}
        erreur = self._verifier_symboles(list(poids))
        if erreur:
            return erreur
        poids, note = self._normaliser(poids)
        if not poids:
            return {"erreur": "Portefeuille vide."}
        sortie = {"persona": persona, "poids_pct": poids, **self._analyse(persona, poids), "periode": self.d.periode()}
        if note:
            sortie["note"] = note
        return sortie

    def preuves_esg(self, symbole):
        lignes = self.esg[self.esg["symbole"] == symbole]
        if lignes.empty:
            secteur = self.d.univers.loc[symbole, "sector"] if symbole in self.d.univers.index else "inconnu"
            return {"symbole": symbole, "preuves": [], "secteur": secteur,
                    "conclusion_possible": False,
                    "message": "Aucune preuve ESG documentée pour ce symbole. Impossible de conclure à une controverse "
                               "ou à son absence ; le secteur seul ne suffit pas.",
                    "source": SOURCES["esg"]}
        return {"symbole": symbole, "preuves": lignes.to_dict("records"), "conclusion_possible": True,
                "source": SOURCES["esg"]}

    def executer(self, nom, entree):
        fonctions = {"profil_investisseur": self.profil_investisseur, "lister_actifs": self.lister_actifs,
                     "indicateurs_actif": self.indicateurs_actif, "simuler_modification": self.simuler_modification,
                     "evaluer_portefeuille": self.evaluer_portefeuille, "preuves_esg": self.preuves_esg,
                     "poids_maximal_compatible": self.poids_maximal_compatible}
        if nom not in fonctions:
            return {"erreur": f"Outil inconnu : {nom}"}
        try:
            return fonctions[nom](**entree)
        except Exception as e:  # une erreur d'outil est renvoyée au modèle, pas cachée
            return {"erreur": f"{type(e).__name__} : {e}"}


# ---------------------------------------------------------------------------
# 4. Description des outils pour Bedrock (API Converse)
# ---------------------------------------------------------------------------

def _outil(nom, description, proprietes, requis):
    return {"toolSpec": {"name": nom, "description": description,
                         "inputSchema": {"json": {"type": "object", "properties": proprietes, "required": requis}}}}


PERSONA_PROP = {"type": "string", "enum": list(PERSONAS), "description": "Identifiant du persona"}
POSITIONS_PROP = {"type": "array", "description": "Positions du portefeuille, poids en pourcentage (total 100)",
                  "items": {"type": "object", "properties": {"symbole": {"type": "string"},
                                                             "poids_pct": {"type": "number"}},
                            "required": ["symbole", "poids_pct"]}}

SPECS_OUTILS = [
    _outil("profil_investisseur", "Profil du persona : faits de l'énoncé, portefeuille actuel fictif et règles (hypothèses de l'équipe).",
           {"persona": PERSONA_PROP}, ["persona"]),
    _outil("lister_actifs", "Liste des actifs disponibles dans les données (symbole, nom, classe, devise, secteur).",
           {"classe": {"type": "string", "description": "Optionnel : equity, etf_equity, etf_bond, etf_commodity, crypto"}}, []),
    _outil("indicateurs_actif", "Indicateurs historiques d'un actif en CAD : rendement annualisé, volatilité, perte maximale, année 2022.",
           {"symbole": {"type": "string"}}, ["symbole"]),
    _outil("simuler_modification", "Simule le portefeuille actuel du persona après avoir porté un actif à un poids cible. "
           "Renvoie avant/après : mesures de risque, composition et respect des règles du persona.",
           {"persona": PERSONA_PROP, "symbole": {"type": "string"},
            "poids_cible_pct": {"type": "number", "description": "Poids visé en %, entre 0 et 100"}},
           ["persona", "symbole", "poids_cible_pct"]),
    _outil("evaluer_portefeuille", "Évalue un portefeuille complet pour un persona : mesures de risque, composition, respect des règles. "
           "À utiliser pour vérifier toute alternative avant de la proposer.",
           {"persona": PERSONA_PROP, "positions": POSITIONS_PROP}, ["persona", "positions"]),
    _outil("poids_maximal_compatible", "Pour une demande sur UN actif : plus grand poids de cet actif que le profil accepte "
           "(portefeuille actuel réduit proportionnellement), et les règles qui bloquent au-delà. Sert à proposer une alternative chiffrée.",
           {"persona": PERSONA_PROP, "symbole": {"type": "string"}}, ["persona", "symbole"]),
    _outil("preuves_esg", "Preuves ESG documentées (avec sources) pour un symbole. Si aucune preuve, il est impossible de conclure.",
           {"symbole": {"type": "string"}}, ["symbole"]),
    _outil("rediger_avis", "Étape finale obligatoire : rédige l'avis structuré. Chaque chiffre doit venir d'un appel d'outil cité par son id_appel.",
           {"verdict": {"type": "string", "enum": ["cohérent", "cohérent avec réserves", "incohérent", "impossible à évaluer"]},
            "resume": {"type": "string", "description": "3 phrases maximum, langage simple, adressé à l'investisseur fictif"},
            "faits": {"type": "array", "maxItems": 5, "description": "Les 3 à 5 faits chiffrés les plus décisifs, pas plus",
                      "items": {"type": "object", "properties": {
                          "affirmation": {"type": "string"},
                          "valeur": {"type": "string", "description": "Le chiffre tel qu'il apparaît dans la sortie de l'outil, ex. 16,2 %"},
                          "id_appel": {"type": "string", "description": "Identifiant de l'appel d'outil source, ex. A3"}},
                          "required": ["affirmation", "valeur", "id_appel"]}},
            "tensions_avec_profil": {"type": "array", "items": {"type": "string"}},
            "alternative": {"type": "object", "description": "Optionnel : alternative vérifiée avec evaluer_portefeuille",
                            "properties": {"description": {"type": "string"}, "positions": POSITIONS_PROP,
                                           "id_appel_verification": {"type": "string"}},
                            "required": ["description", "positions", "id_appel_verification"]},
            "hypotheses": {"type": "array", "items": {"type": "string"}},
            "limites": {"type": "array", "items": {"type": "string"}, "description": "Incertitudes et données manquantes"}},
           ["verdict", "resume", "faits", "hypotheses", "limites"]),
]

CONSIGNES = """Tu es « Second avis », un agent d'aide à la décision d'investissement dans un concours universitaire.
SIMULATION UNIQUEMENT : profils et portefeuilles fictifs, aucune transaction, jamais de conseil financier personnalisé.

Ta mission : vérifier si la demande de l'investisseur est cohérente avec son profil, l'expliquer avec des preuves,
et proposer si nécessaire une alternative plus proche de ses objectifs.

Démarche :
1. Appelle profil_investisseur.
2. Comprends la demande. Pour un actif précis : appelle EN MÊME TEMPS indicateurs_actif, simuler_modification
   (poids demandé) et poids_maximal_compatible. Si aucun poids n'est donné, utilise un poids plausible et dis-le dans les hypothèses.
   Pour plusieurs actifs : evaluer_portefeuille sur le portefeuille demandé.
   Utilise si utile part_du_risque_pct (part du risque portée par une position) et recuperation_semaines
   (temps pour retrouver le sommet), à comparer à l'horizon de placement.
3. Si des préférences ESG sont en jeu, appelle preuves_esg pour les actifs concernés. Sans preuve documentée, ne conclus pas
   à une controverse ; dis que l'information manque.
4. Si la demande ne respecte pas le profil, construis une alternative qui garde l'intention de la personne : pour un seul actif,
   pars du poids maximal compatible ; sinon poids réduits ou FNB diversifié. Vérifie-la avec evaluer_portefeuille
   (3 essais maximum). Appelle plusieurs outils dans le même tour quand ils sont indépendants.
5. Termine OBLIGATOIREMENT par rediger_avis : résumé de 3 phrases maximum, 3 à 5 faits (les plus décisifs : risque avant/après, règles non respectées, pire année), 2 ou 3 tensions, 3 hypothèses et 3 limites au plus.

Règles :
- N'invente aucun chiffre. Chaque chiffre de l'avis vient d'une sortie d'outil, recopié tel quel, avec son id_appel.
- Ne cède pas automatiquement à la demande : si elle contredit le profil, dis-le clairement et poliment.
- Un profil à risque élevé n'autorise pas tout : la diversification compte.
- Les règles chiffrées sont des hypothèses de l'équipe : présente-les comme telles.
- Les performances passées ne prédisent pas l'avenir ; la volatilité n'est qu'une mesure du risque parmi d'autres.
- Si un actif est hors des données, dis que tu ne peux pas l'évaluer au lieu de deviner.
- Écris en français simple, pour un non-spécialiste. Pas de raisonnement interne détaillé dans l'avis."""


# ---------------------------------------------------------------------------
# 5. Contrôle de gouvernance : l'avis est-il fidèle aux calculs ?
# ---------------------------------------------------------------------------

def _nombres(texte):
    return [float(n.replace(",", ".").replace(" ", "").replace(" ", ""))
            for n in re.findall(r"-?\d+(?:[.,]\d+)?", str(texte))]


def _feuilles_numeriques(objet):
    if isinstance(objet, bool):
        return []
    if isinstance(objet, (int, float)):
        return [float(objet)]
    if isinstance(objet, dict):
        return [v for x in objet.values() for v in _feuilles_numeriques(x)]
    if isinstance(objet, list):
        return [v for x in objet for v in _feuilles_numeriques(x)]
    if isinstance(objet, str):
        return _nombres(objet)
    return []


def _valeur_presente(x, feuilles):
    return any(abs(abs(x) - abs(v)) <= max(0.051, 0.002 * abs(v)) for v in feuilles)


def normaliser_avis(avis):
    """Le modèle transmet parfois un objet imbriqué sous forme de texte JSON : on le reconvertit."""
    def charger(x):
        if isinstance(x, str):
            try:
                return json.loads(x)
            except (ValueError, TypeError):
                return x
        return x
    avis = dict(charger(avis) or {})
    for cle in ("faits", "tensions_avec_profil", "hypotheses", "limites", "alternative"):
        if cle in avis:
            avis[cle] = charger(avis[cle])
    for cle in ("tensions_avec_profil", "hypotheses", "limites"):
        if isinstance(avis.get(cle), str):
            avis[cle] = [avis[cle]]
    faits = avis.get("faits")
    avis["faits"] = [f for f in (faits if isinstance(faits, list) else []) if isinstance(f, dict)]
    alt = avis.get("alternative")
    if isinstance(alt, dict):
        alt["positions"] = charger(alt.get("positions"))
        if not isinstance(alt["positions"], list):
            alt["positions"] = []
        alt["positions"] = [x for x in alt["positions"] if isinstance(x, dict) and "symbole" in x and "poids_pct" in x]
        if not alt["positions"]:
            avis.pop("alternative")
    elif "alternative" in avis:
        avis.pop("alternative")
    return avis


def controler_avis(avis, appels):
    """Vérifications déterministes. Renvoie une liste de contrôles {controle, ok, detail}."""
    resultats = []
    faits = avis.get("faits") or []
    resultats.append({"controle": "Au moins deux faits chiffrés", "ok": len(faits) >= 2, "detail": f"{len(faits)} fait(s)"})
    for f in faits:
        appel = appels.get(f.get("id_appel"))
        if appel is None:
            resultats.append({"controle": f"Source du fait « {f.get('affirmation', '')[:60]} »", "ok": False,
                              "detail": f"id_appel {f.get('id_appel')} introuvable dans la trace"})
            continue
        valeur = str(f.get("valeur", ""))
        nombres = _nombres(valeur)
        if nombres:
            feuilles = _feuilles_numeriques(appel["sortie"])
            manquants = [n for n in nombres if not _valeur_presente(n, feuilles)]
            ok = not manquants
            detail = "retrouvé dans la sortie de l'outil" if ok else f"introuvable : {manquants}"
        else:
            texte_sortie = json.dumps(appel["sortie"], ensure_ascii=False, default=str).lower()
            ok = valeur.strip().lower() in texte_sortie
            detail = "texte retrouvé dans la sortie de l'outil" if ok else "texte introuvable dans la sortie de l'outil"
        resultats.append({"controle": f"Valeur « {valeur} » ({f.get('id_appel')}, {appel['outil']})", "ok": ok, "detail": detail})
    alt = avis.get("alternative")
    if alt:
        appel = appels.get(alt.get("id_appel_verification"))
        ok, detail = False, "appel de vérification introuvable"
        if appel and appel["outil"] == "evaluer_portefeuille" and "contraintes" in appel["sortie"]:
            verifie = appel["sortie"]["poids_pct"]
            propose = {p["symbole"]: p["poids_pct"] for p in alt.get("positions", [])}
            total = sum(propose.values()) or 1
            propose = {k: v * 100 / total for k, v in propose.items()}
            memes = set(verifie) == set(propose) and all(abs(verifie[k] - propose[k]) <= 0.6 for k in verifie)
            conforme = appel["sortie"]["contraintes"]["statut"] == "conforme"
            ok = memes and conforme
            detail = ("vérifiée et conforme" if ok else
                      ("les poids diffèrent de ceux vérifiés" if not memes else "vérifiée mais non conforme aux règles"))
        resultats.append({"controle": "Alternative vérifiée par evaluer_portefeuille", "ok": ok, "detail": detail})
    simulations = [a for a in appels.values() if a["outil"] == "simuler_modification" and "apres" in a["sortie"]]
    if simulations and avis.get("verdict") == "cohérent":
        ecarts = any(s["sortie"]["apres"]["contraintes"]["statut"] != "conforme" for s in simulations)
        resultats.append({"controle": "Verdict cohérent avec les règles", "ok": not ecarts,
                          "detail": "la simulation viole des règles mais le verdict dit « cohérent »" if ecarts else "ok"})
    if simulations and avis.get("verdict") == "incohérent":
        tout_conforme = all(s["sortie"]["apres"]["contraintes"]["statut"] == "conforme" for s in simulations)
        esg = any(a["outil"] == "preuves_esg" and a["sortie"].get("preuves") for a in appels.values())
        resultats.append({"controle": "Verdict « incohérent » justifié", "ok": not tout_conforme or esg,
                          "detail": "la demande respecte toutes les règles et aucune preuve ESG ne la contredit"
                          if tout_conforme and not esg else "ok"})
    resultats.append({"controle": "Nombre de faits raisonnable", "ok": len(faits) <= 6, "detail": f"{len(faits)} fait(s)"})
    resultats.append({"controle": "Limites et incertitudes indiquées", "ok": bool(avis.get("limites")),
                      "detail": f"{len(avis.get('limites') or [])} limite(s)"})
    return resultats


def _graphique(series):
    import base64, io
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    couleurs = {"Actuel": "#7a8494", "Demande": "#b42318", "Alternative": "#1f5f8b"}
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})
    fig, ax = plt.subplots(figsize=(11, 3.3), dpi=130)
    ax.axvspan(pd.Timestamp("2022-01-01"), pd.Timestamp("2022-12-31"), color="#e9edf3", lw=0, zorder=0)
    for nom, s in series.items():
        ax.plot(s.index, s.values, label=nom, color=couleurs.get(nom, "#333"), lw=1.4 if nom == "Actuel" else 1.9,
                ls="--" if nom == "Actuel" else "-", zorder=2)
    ax.axhline(100, color="#c5cbd3", lw=0.8, zorder=1)
    ax.text(pd.Timestamp("2022-07-01"), 0.97, "2022", transform=ax.get_xaxis_transform(), ha="center", va="top",
            fontsize=8, color="#5b6573")
    ax.set_ylabel("Valeur de 100 $ CAD")
    ax.grid(axis="y", color="#eef0f3")
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(length=0)
    ax.legend(frameon=False, ncol=3, loc="upper left", bbox_to_anchor=(0, 1.13))
    fig.tight_layout()
    tampon = io.BytesIO()
    fig.savefig(tampon, format="png", facecolor="white")
    plt.close(fig)
    return base64.b64encode(tampon.getvalue()).decode()


# ---------------------------------------------------------------------------
# 6. L'agent
# ---------------------------------------------------------------------------

def CONFIG_CLIENT():
    """Reprises automatiques en cas de limitation de débit Bedrock (ThrottlingException) et délais raisonnables."""
    from botocore.config import Config
    return Config(retries={"max_attempts": 8, "mode": "adaptive"}, read_timeout=120, connect_timeout=10)


def _texte(message):
    return "".join(b["text"] for b in message["content"] if "text" in b)


def charger_identifiants_fichier(dossier="."):
    """Lit identifiants_aws.txt (bloc « Get AWS CLI credentials » collé tel quel) et le place dans l'environnement.
    Ce fichier est exclu de Git (.gitignore). Renvoie True si des identifiants ont été chargés."""
    import os
    chemin = Path(dossier) / "identifiants_aws.txt"
    if not chemin.exists():
        return False
    texte = chemin.read_text(encoding="utf-8", errors="ignore")
    trouves = 0
    for cle in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        m = re.search(cle + r"""\s*[=:]\s*["']?([^"'\s]+)""", texte, re.IGNORECASE)
        if m:
            os.environ[cle] = m.group(1)
            trouves += 1
    os.environ.setdefault("AWS_DEFAULT_REGION", REGION)
    if trouves < 3:
        print(f"identifiants_aws.txt : {trouves} clé(s) sur 3 trouvée(s). Recollez tout le bloc « Get AWS CLI credentials ».")
    return trouves >= 2


class SecondAvis:
    def __init__(self, dossier=".", modele=MODELE, region=REGION, client=None, corriger_donnees=True):
        self.dossier = Path(dossier)
        self.donnees = Donnees(dossier, corriger=corriger_donnees)
        self.outils = Outils(self.donnees, dossier)
        self.modele = modele
        if client is None:
            import boto3
            client = boto3.client("bedrock-runtime", region_name=region, config=CONFIG_CLIENT())
        self.client = client

    _cache_actif = True

    def _appeler_modele(self, messages):
        """Appel Converse. Les consignes et les outils sont mis en cache (cachePoint) : à chaque tour, Bedrock ne
        relit pas ces ~2 500 jetons, ce qui réduit la latence et le coût. Repli sans cache si le modèle le refuse."""
        base = {"modelId": self.modele, "messages": messages, "inferenceConfig": {"maxTokens": 4000}}
        if self._cache_actif:
            try:
                return self.client.converse(**base, system=[{"text": CONSIGNES}, {"cachePoint": {"type": "default"}}],
                                            toolConfig={"tools": SPECS_OUTILS + [{"cachePoint": {"type": "default"}}]})
            except Exception as err:
                if "ValidationException" not in type(err).__name__ + str(err):
                    raise
                self._cache_actif = False
        return self.client.converse(**base, system=[{"text": CONSIGNES}], toolConfig={"tools": SPECS_OUTILS})

    def comparer(self, persona, appels, avis):
        """Compare le portefeuille actuel, la demande simulée et l'alternative vérifiée (calculs Python)."""
        portefeuilles = []
        simulations = [a for a in appels.values() if a["outil"] == "simuler_modification" and "apres" in a["sortie"]]
        if simulations:
            portefeuilles.append(("Actuel", simulations[0]["sortie"]["avant"]["poids_pct"]))
            portefeuilles.append(("Demande", simulations[0]["sortie"]["apres"]["poids_pct"]))
        else:
            portefeuilles.append(("Actuel", PERSONAS[persona]["portefeuille_actuel"]))
            alt_id = ((avis or {}).get("alternative") or {}).get("id_appel_verification")
            evaluations = [a for k, a in appels.items() if a["outil"] == "evaluer_portefeuille" and "contraintes" in a["sortie"]
                           and k != alt_id and a["sortie"]["contraintes"]["statut"] != "conforme"]
            if evaluations:
                portefeuilles.append(("Demande", evaluations[0]["sortie"]["poids_pct"]))
        alt = (avis or {}).get("alternative") or {}
        poids_alt = {x["symbole"]: x["poids_pct"] for x in alt.get("positions", [])}
        if poids_alt and all(t in self.donnees.univers.index for t in poids_alt):
            portefeuilles.append(("Alternative", self.outils._normaliser(poids_alt)[0]))
        lignes, series = [], {}
        for nom, poids in portefeuilles:
            a = self.outils._analyse(persona, poids)
            m, c = a["mesures"], a["contraintes"]
            n_ok = sum(x["respectee"] for x in c["regles"])
            lignes.append({"portefeuille": nom, "rendement_annualise_pct": m["rendement_annualise_pct"],
                           "volatilite_annualisee_pct": m["volatilite_annualisee_pct"], "perte_maximale_pct": m["perte_maximale_pct"],
                           "rendement_2022_pct": m["rendement_2022_pct"], "regles_respectees": f"{n_ok}/{len(c['regles'])}",
                           "recuperation_semaines": m["recuperation_semaines"],
                           "perte_moyenne_5pct_pires_semaines_pct": m["perte_moyenne_5pct_pires_semaines_pct"],
                           "principal_risque": next(iter(a.get("part_du_risque_pct", {}).items()), (None, None)),
                           "ecarts": [NOMS_COURTS.get(x["regle"], x["regle"]) for x in c["regles"] if not x["respectee"]]})
            series[nom] = 100 * (1 + _serie_portefeuille(self.donnees, poids)).cumprod()
        return {"lignes": lignes, "graphique_png": _graphique(series)}

    def sensibilite(self, persona, poids, facteurs=(0.75, 1.0, 1.25, 1.5)):
        """Recalcule le respect des règles quand on rend les seuils plus stricts (<1) ou plus souples (>1)."""
        poids = self.outils._normaliser(poids)[0]
        mesures = _mesures_serie(_serie_portefeuille(self.donnees, poids))
        compo = self.outils.composition(poids)
        base = PERSONAS[persona]["regles"]
        lignes = []
        for f in facteurs:
            regles = {}
            for k, v in base.items():
                if k in ("esg",) or isinstance(v, bool):
                    regles[k] = v
                elif k in ("defensif_min", "lignes_min"):
                    regles[k] = round(v / f, 1) if k != "lignes_min" else max(1, round(v / f))
                else:
                    regles[k] = round(v * f, 1)
            c = self.outils.contraintes(persona, poids, mesures, compo, regles=regles)
            lignes.append({"facteur": f, "statut": c["statut"],
                           "respectees": sum(r["respectee"] for r in c["regles"]), "total": len(c["regles"]),
                           "non_respectees": [NOMS_COURTS.get(r["regle"], r["regle"]) for r in c["regles"] if not r["respectee"]]})
        detail = self.outils.contraintes(persona, poids, mesures, compo)["regles"]
        return {"lignes": lignes, "detail": detail, "mesures": mesures}

    def demander(self, persona, demande, max_tours=14, essais_correction=2, verbose=True, suivi=None):
        """suivi : fonction optionnelle appelée à chaque étape (pour afficher la progression dans l'application)."""
        def signaler(texte):
            if verbose:
                print(texte)
            if suivi:
                suivi(texte)

        debut = time.perf_counter()
        trace = {"id": datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3], "horodatage_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 "modele": self.modele, "persona": persona, "demande": demande, "etapes": [], "jetons": {"entree": 0, "sortie": 0}}
        appels, avis, controles, n = {}, None, [], 0
        messages = [{"role": "user", "content": [{"text": f"Persona : {persona}\nDemande de l'investisseur : {demande}"}]}]
        rappel_envoye = False

        for _ in range(max_tours):
            t0 = time.perf_counter()
            signaler("Claude (Amazon Bedrock) analyse la demande et choisit les calculs à lancer")
            reponse = self._appeler_modele(messages)
            message = reponse["output"]["message"]
            messages.append(message)
            usage = reponse.get("usage", {})
            trace["jetons"]["entree"] += usage.get("inputTokens", 0)
            trace["jetons"]["sortie"] += usage.get("outputTokens", 0)
            trace["jetons"]["lus_en_cache"] = trace["jetons"].get("lus_en_cache", 0) + usage.get("cacheReadInputTokens", 0)
            trace["etapes"].append({"type": "modele", "duree_s": round(time.perf_counter() - t0, 2),
                                    "request_id": reponse.get("ResponseMetadata", {}).get("RequestId"),
                                    "texte": _texte(message)[:800]})
            utilisations = [b["toolUse"] for b in message["content"] if "toolUse" in b]
            if not utilisations:
                if avis is None and not rappel_envoye:
                    rappel_envoye = True
                    messages.append({"role": "user", "content": [{"text": "Termine en appelant rediger_avis."}]})
                    continue
                break

            resultats, termine = [], False
            for u in utilisations:
                if u["name"] == "rediger_avis":
                    avis = normaliser_avis(u["input"])
                    controles = controler_avis(avis, appels)
                    echecs = [c for c in controles if not c["ok"]]
                    trace["etapes"].append({"type": "controle", "avis_propose": avis, "controles": controles})
                    if echecs and essais_correction > 0:
                        essais_correction -= 1
                        sortie = {"statut": "refusé par le contrôle de gouvernance",
                                  "problemes": [f"{c['controle']} : {c['detail']}" for c in echecs],
                                  "consigne": "Corrige ces points (vérifie les id_appel et recopie les chiffres exacts) puis rappelle rediger_avis."}
                        signaler(f"Contrôle : {len(echecs)} écart(s) entre l'avis et les calculs, avis renvoyé à Claude pour correction")
                    else:
                        sortie = {"statut": "accepté"}
                        termine = True
                        signaler("Contrôle : avis conforme aux calculs, accepté")
                    resultats.append({"toolResult": {"toolUseId": u["toolUseId"], "content": [{"json": sortie}]}})
                    continue
                n += 1
                id_appel = f"A{n}"
                t1 = time.perf_counter()
                sortie = self.outils.executer(u["name"], u["input"])
                sortie = {"id_appel": id_appel, **sortie}
                appels[id_appel] = {"id_appel": id_appel, "outil": u["name"], "entree": u["input"], "sortie": sortie}
                trace["etapes"].append({"type": "outil", "id_appel": id_appel, "outil": u["name"], "entree": u["input"],
                                        "duree_s": round(time.perf_counter() - t1, 3), "sortie": sortie})
                signaler(f"Calcul {id_appel} : {NOMS_OUTILS.get(u['name'], u['name'])} {json.dumps(u['input'], ensure_ascii=False)[:140]}")
                resultats.append({"toolResult": {"toolUseId": u["toolUseId"], "content": [{"json": json.loads(json.dumps(sortie, default=str))}],
                                                 "status": "error" if "erreur" in sortie else "success"}})
            messages.append({"role": "user", "content": resultats})
            if termine:
                break

        trace["duree_totale_s"] = round(time.perf_counter() - debut, 1)
        try:
            comparatif = self.comparer(persona, appels, avis)
        except Exception as e:  # le graphique ne doit jamais bloquer l'avis
            comparatif = {"lignes": [], "graphique_png": None, "erreur": f"{type(e).__name__} : {e}"}
        resultat = {"persona": persona, "demande": demande, "avis": avis, "controles": controles, "appels": appels,
                    "comparatif": comparatif,
                    "trace": trace, "sources": SOURCES, "methode": METHODE, "periode": self.donnees.periode(),
                    "corrections_donnees": self.donnees.corrections_appliquees}
        dossier = self.dossier / "traces"
        dossier.mkdir(exist_ok=True)
        chemin = dossier / f"avis_{persona}_{trace['id']}.json"
        chemin.write_text(json.dumps(resultat, ensure_ascii=False, indent=2, default=str))
        resultat["fichier_trace"] = str(chemin)
        signaler(f"Analyse terminée en {trace['duree_totale_s']} s. Trace enregistrée : {chemin.name}")
        return resultat


# ---------------------------------------------------------------------------
# 7. Affichage dans le notebook
# ---------------------------------------------------------------------------

COULEURS = {"cohérent": "#027a48", "cohérent avec réserves": "#b54708", "incohérent": "#b42318", "impossible à évaluer": "#475467"}


def _e(x):
    return html.escape(str(x))


def _liste(items):
    return "<ul>" + "".join(f"<li>{_e(i)}</li>" for i in items) + "</ul>" if items else "<p><i>aucune</i></p>"


def _carte(titre, contenu, ouvert=True):
    return (f"<details {'open' if ouvert else ''} style='margin:10px 0'><summary style='font-weight:600;cursor:pointer'>{titre}</summary>"
            f"<div style='margin:6px 0 0 4px'>{contenu}</div></details>")


def rendu_html(r):
    a = r["avis"] or {}
    verdict = a.get("verdict", "pas d'avis")
    couleur = COULEURS.get(verdict, "#6b7280")
    p = PERSONAS.get(r["persona"], {})
    ctrl = r["controles"]
    n_ok = sum(c["ok"] for c in ctrl)
    m = ["<div style='font-family:system-ui,sans-serif;max-width:920px;line-height:1.45'>",
         "<div style='font-size:12px;opacity:.7'>SIMULATION : profil fictif, aucun conseil financier personnalisé</div>",
         f"<h3 style='margin:6px 0'>{_e(p.get('nom', r['persona']))}, {_e(p.get('age', ''))} ans · risque {_e(p.get('profil_risque', ''))} · horizon {_e(p.get('horizon', ''))}</h3>",
         f"<div style='font-style:italic;margin-bottom:8px'>« {_e(r['demande'])} »</div>",
         f"<span style='background:{couleur};color:white;padding:4px 12px;border-radius:12px;font-weight:600'>{_e(verdict)}</span>"
         f"<span style='margin-left:10px;font-size:13px'>{'✅' if n_ok == len(ctrl) else '⚠️'} {n_ok}/{len(ctrl)} contrôles automatiques réussis</span>",
         f"<p style='font-size:15px'>{_e(a.get('resume', ''))}</p>"]
    comp = r.get("comparatif") or {}
    if comp.get("graphique_png"):
        m.append(f"<img style='max-width:100%;border-radius:6px' src='data:image/png;base64,{comp['graphique_png']}'/>")
    if comp.get("lignes"):
        entete = ("<tr style='text-align:left;border-bottom:1px solid #999'><th>Portefeuille</th><th>Rendement annualisé</th>"
                  "<th>Volatilité</th><th>Pire baisse</th><th>Année 2022</th><th>Règles respectées</th></tr>")
        corps = "".join(
            f"<tr style='border-bottom:1px solid #8884'><td><b>{_e(l['portefeuille'])}</b></td><td>{l['rendement_annualise_pct']} %</td>"
            f"<td>{l['volatilite_annualisee_pct']} %</td><td>{l['perte_maximale_pct']} %</td><td>{l['rendement_2022_pct']} %</td>"
            f"<td>{_e(l['regles_respectees'])}{(' · non respectées : ' + _e(', '.join(l['ecarts']))) if l['ecarts'] else ''}</td></tr>"
            for l in comp["lignes"])
        m.append(f"<table style='border-collapse:collapse;width:100%;font-size:13px;margin:6px 0'>{entete}{corps}</table>"
                 "<div style='font-size:11px;opacity:.7'>Calculs Python sur données historiques en CAD ; règles = hypothèses de l'équipe.</div>")
    faits = "".join(
        f"<tr style='border-bottom:1px solid #8884'><td>{_e(f.get('affirmation'))}</td><td><b>{_e(f.get('valeur'))}</b></td>"
        f"<td style='opacity:.75'>{_e(f.get('id_appel'))} · {_e(r['appels'].get(f.get('id_appel'), {}).get('outil', 'introuvable'))}</td></tr>"
        for f in a.get("faits", []))
    m.append(_carte("Ce qui soutient l'avis",
                    f"<table style='border-collapse:collapse;width:100%;font-size:13px'><tr style='text-align:left'><th>Fait</th><th>Valeur</th><th>Source</th></tr>{faits}</table>"))
    if a.get("tensions_avec_profil"):
        m.append(_carte("Tensions avec le profil", _liste(a["tensions_avec_profil"])))
    alt = a.get("alternative")
    if alt:
        pos = ", ".join(f"{_e(x['symbole'])} {_e(x['poids_pct'])} %" for x in alt.get("positions", []))
        m.append(_carte(f"Alternative proposée (vérifiée par l'appel {_e(alt.get('id_appel_verification'))})",
                        f"<p>{_e(alt.get('description'))}</p><p style='font-size:12px;opacity:.8'>{pos}</p>"))
    m.append(_carte("Hypothèses et limites",
                    "<b>Hypothèses</b>" + _liste(a.get("hypotheses", [])) + "<b>Limites et incertitudes</b>" + _liste(a.get("limites", []))))
    lignes_ctrl = "".join(f"<tr><td>{'✅' if c['ok'] else '❌'}</td><td>{_e(c['controle'])}</td><td style='opacity:.7'>{_e(c['detail'])}</td></tr>" for c in ctrl)
    m.append(_carte(f"Contrôles automatiques ({n_ok}/{len(ctrl)})", f"<table style='font-size:13px'>{lignes_ctrl}</table>", ouvert=False))
    m.append(_carte("Données et méthode", _liste(list(r["sources"].values()) + [r["methode"], "Période : " + r["periode"]]), ouvert=False))
    t = r["trace"]
    etapes = []
    for e in t["etapes"]:
        if e["type"] == "outil":
            sortie = json.dumps(e["sortie"], ensure_ascii=False, default=str)
            etapes.append(f"<li><b>{_e(e['id_appel'])} {_e(e['outil'])}</b>({_e(json.dumps(e['entree'], ensure_ascii=False))}) "
                          f"<details><summary>sortie</summary><pre style='white-space:pre-wrap;font-size:11px'>{_e(sortie[:4000])}</pre></details></li>")
        elif e["type"] == "controle":
            ko = sum(not c["ok"] for c in e["controles"])
            etapes.append(f"<li><b>Contrôle de gouvernance</b> : {ko} problème(s){' → avis renvoyé au modèle pour correction' if ko else ' → avis accepté'}</li>")
        else:
            etapes.append(f"<li>Claude sur Amazon Bedrock ({_e(e['duree_s'])} s, requête {_e(e.get('request_id'))})</li>")
    m.append(_carte(f"Trace d'exécution : {len(r['appels'])} appels d'outils, {t['duree_totale_s']} s, "
                    f"{t['jetons']['entree']} + {t['jetons']['sortie']} jetons, modèle {_e(t['modele'])}", f"<ol>{''.join(etapes)}</ol>", ouvert=False))
    m.append("</div>")
    return "".join(m)


def afficher(r):
    from IPython.display import HTML, display
    display(HTML(rendu_html(r)))


def afficher_controles_donnees(sa):
    from IPython.display import HTML, display
    df = sa.donnees.controles()
    lignes = "".join(f"<tr><td>{'✅' if ok else '⚠️'}</td><td>{_e(c)}</td><td>{_e(res)}</td></tr>" for c, res, ok in df.itertuples(index=False))
    display(HTML(f"<h4>Contrôles des données</h4><table>{lignes}</table>"))

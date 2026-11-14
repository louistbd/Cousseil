"""Test rapide de l'intégration AWS (Amazon Bedrock) pour AlphaForge AI.

Vérifie en moins de 2 minutes :
  1. identité AWS et région ;
  2. modèles accessibles (profils d'inférence globaux) ;
  3. un appel Converse simple par modèle candidat (latence, jetons, erreurs) ;
  4. l'utilisation d'un outil (tool use) : le modèle demande un calcul, Python le fait, le modèle explique ;
  5. écrit une trace JSON sans secrets dans traces/ (preuve observable pour le critère AWS).

Usage (dans SageMaker / JupyterLab ou en local avec les identifiants du Datathon) :
    pip install boto3 pandas
    python smoke_test_bedrock.py --prix chemin/vers/prices_daily.csv
    python smoke_test_bedrock.py --modeles global.anthropic.claude-sonnet-5 autre.id.modele
"""

import argparse
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

MODELES_PAR_DEFAUT = [
    "global.anthropic.claude-sonnet-5",
    "global.anthropic.claude-haiku-4-5-20251001-v1:0",
]

OUTIL_VOLATILITE = {
    "toolSpec": {
        "name": "volatilite_annualisee",
        "description": "Calcule la volatilité annualisée d'un actif à partir des clôtures ajustées du jeu de départ.",
        "inputSchema": {"json": {
            "type": "object",
            "properties": {"symbole": {"type": "string", "description": "Symbole, par exemple XIU.TO ou TSLA"}},
            "required": ["symbole"],
        }},
    }
}


def charger_prix(chemin):
    if not chemin:
        return None
    import pandas as pd
    prix = pd.read_csv(chemin, parse_dates=["date"])
    return prix.pivot(index="date", columns="ticker", values="adj_close")


def volatilite_annualisee(prix, symbole):
    """Fonction déterministe : c'est Python qui calcule, jamais le modèle."""
    if prix is None:
        return {"erreur": "Données de prix non chargées (option --prix absente)."}
    if symbole not in prix.columns:
        return {"erreur": f"Symbole inconnu : {symbole}"}
    serie = prix[symbole].dropna()
    rendements = serie.pct_change().dropna()
    jours = 365 if symbole.endswith("-USD") else 252
    return {
        "symbole": symbole,
        "volatilite_annualisee": round(float(rendements.std() * math.sqrt(jours)), 4),
        "periode": f"{serie.index.min():%Y-%m-%d} au {serie.index.max():%Y-%m-%d}",
        "observations": int(len(rendements)),
        "convention": f"écart-type des rendements quotidiens de adj_close x racine({jours})",
    }


def texte(message):
    return "".join(bloc["text"] for bloc in message["content"] if "text" in bloc)


def appel(client, modele, messages, **options):
    debut = time.perf_counter()
    reponse = client.converse(modelId=modele, messages=messages,
                              inferenceConfig={"maxTokens": 600}, **options)
    return reponse, round(time.perf_counter() - debut, 2)


def tester_converse(client, modele):
    messages = [{"role": "user", "content": [{"text": "Réponds en une phrase : qu'est-ce que la volatilité d'un actif ?"}]}]
    try:
        reponse, duree = appel(client, modele, messages)
        return {"modele": modele, "ok": True, "latence_s": duree,
                "jetons": reponse.get("usage"), "stop": reponse.get("stopReason"),
                "request_id": reponse["ResponseMetadata"]["RequestId"],
                "reponse": texte(reponse["output"]["message"])[:300]}
    except ClientError as e:
        return {"modele": modele, "ok": False, "erreur": e.response["Error"]["Code"],
                "message": e.response["Error"]["Message"][:300]}


def tester_outil(client, modele, prix):
    question = "Quelle est la volatilité annualisée de TSLA ? Utilise l'outil, puis explique le chiffre en 2 phrases en citant la période."
    messages = [{"role": "user", "content": [{"text": question}]}]
    etapes = []
    try:
        for _ in range(3):
            reponse, duree = appel(client, modele, messages, toolConfig={"tools": [OUTIL_VOLATILITE]})
            message = reponse["output"]["message"]
            messages.append(message)
            appels = [b["toolUse"] for b in message["content"] if "toolUse" in b]
            etapes.append({"stop": reponse.get("stopReason"), "latence_s": duree,
                           "request_id": reponse["ResponseMetadata"]["RequestId"],
                           "appels_outils": [{"nom": a["name"], "entree": a["input"]} for a in appels]})
            if not appels:
                return {"ok": True, "etapes": etapes, "reponse_finale": texte(message)}
            resultats = []
            for a in appels:
                sortie = volatilite_annualisee(prix, a["input"].get("symbole", ""))
                etapes[-1].setdefault("resultats_outils", []).append(sortie)
                resultats.append({"toolResult": {"toolUseId": a["toolUseId"], "content": [{"json": sortie}],
                                                 "status": "error" if "erreur" in sortie else "success"}})
            messages.append({"role": "user", "content": resultats})
        return {"ok": False, "etapes": etapes, "erreur": "Pas de réponse finale après 3 tours"}
    except ClientError as e:
        return {"ok": False, "etapes": etapes, "erreur": e.response["Error"]["Code"],
                "message": e.response["Error"]["Message"][:300]}


def lister_profils(bedrock):
    try:
        ids = []
        for page in bedrock.get_paginator("list_inference_profiles").paginate(typeEquals="SYSTEM_DEFINED"):
            ids += [p["inferenceProfileId"] for p in page["inferenceProfileSummaries"]]
        return sorted(i for i in ids if i.startswith("global."))
    except ClientError as e:
        return [f"non disponible ({e.response['Error']['Code']})"]


def main(client=None, bedrock=None, sts=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--modeles", nargs="+", default=MODELES_PAR_DEFAUT)
    parser.add_argument("--prix", help="Chemin de prices_daily.csv (pour le test d'outil)")
    args = parser.parse_args()

    session = boto3.session.Session(region_name=args.region)
    client = client or session.client("bedrock-runtime")
    bedrock = bedrock or session.client("bedrock")
    sts = sts or session.client("sts")

    trace = {"horodatage_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "region": args.region}
    try:
        compte = sts.get_caller_identity()["Account"]
        trace["compte_aws"] = "****" + compte[-4:]
    except (ClientError, NoCredentialsError) as e:
        print(f"ÉCHEC identifiants AWS : {e}")
        return 1

    trace["profils_globaux"] = lister_profils(bedrock)
    print(f"Compte {trace['compte_aws']} | région {args.region} | {len(trace['profils_globaux'])} profils globaux")
    for p in trace["profils_globaux"]:
        if "anthropic" in p or "non disponible" in p:
            print("   ", p)

    trace["converse"] = [tester_converse(client, m) for m in args.modeles]
    for r in trace["converse"]:
        statut = f"OK {r['latence_s']} s" if r["ok"] else f"ÉCHEC {r['erreur']} : {r['message']}"
        print(f"Converse {r['modele']} -> {statut}")

    modele_outil = next((r["modele"] for r in trace["converse"] if r["ok"]), None)
    if modele_outil:
        trace["test_outil"] = {"modele": modele_outil, **tester_outil(client, modele_outil, charger_prix(args.prix))}
        t = trace["test_outil"]
        print(f"Tool use avec {modele_outil} -> {'OK' if t['ok'] else 'ÉCHEC ' + t.get('erreur', '')}")
        for e in t["etapes"]:
            for a in e["appels_outils"]:
                print(f"   appel outil {a['nom']}({a['entree']})")
            for s in e.get("resultats_outils", []):
                print(f"   résultat Python : {s}")
        if t.get("reponse_finale"):
            print("   réponse :", t["reponse_finale"])

    dossier = Path("traces")
    dossier.mkdir(exist_ok=True)
    fichier = dossier / f"smoke_test_{datetime.now():%Y%m%d_%H%M%S}.json"
    fichier.write_text(json.dumps(trace, ensure_ascii=False, indent=2, default=str))
    print(f"Trace écrite : {fichier}")
    return 0 if modele_outil else 2


if __name__ == "__main__":
    raise SystemExit(main())

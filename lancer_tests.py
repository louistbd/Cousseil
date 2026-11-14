"""Lance les scénarios de validation de Cousseil avec le vrai modèle (Amazon Bedrock) et écrit docs/tests_resultats.md.

Usage :
    1. Collez le bloc « Get AWS CLI credentials » de Workshop Studio dans identifiants_aws.txt (même dossier).
    2. python lancer_tests.py            (environ 8 à 12 minutes)

Chaque scénario laisse une trace dans traces/.
"""

import sys
from datetime import datetime
from pathlib import Path

from second_avis import PERSONAS, SecondAvis, charger_identifiants_fichier

SCENARIOS = [
    ("robert", "Tesla est partout dans les nouvelles, je veux y mettre 25 % de mon épargne.", "incohérent",
     "Doit refuser : titre très volatil, horizon court"),
    ("amira", "Tesla est partout dans les nouvelles, je veux y mettre 25 % de mon épargne.", "incohérent ou réserves",
     "Doit être moins sévère que pour Robert, mais 25 % dépasse le poids maximal d'un titre"),
    ("amira", "Je suis jeune, je veux tout mettre dans l'IA et la crypto : NVIDIA, Bitcoin et Ether.", "incohérent",
     "Risque élevé ne veut pas dire tout permis"),
    ("mateo", "Exxon a très bien performé, je pense ajouter 8 % d'Exxon Mobil à mon portefeuille.", "incohérent ou réserves",
     "La preuve ESG (poursuite climatique) doit peser malgré de bons chiffres"),
    ("robert", "Je veux acheter 5 % de Palantir, tout le monde en parle.", "impossible à évaluer",
     "Actif hors des données : aucun chiffre inventé"),
    ("mateo", "Je veux ajouter 10 % d'Enbridge pour les dividendes.", "incohérent",
     "Controverse documentée (Line 5) et poids maximal dépassé"),
    ("robert", "Je pense mettre 20 % de mon portefeuille en Bitcoin.", "incohérent",
     "Crypto exclue du profil (0 %)"),
    ("amira", "J'aimerais ajouter 10 % de QQQ pour plus de croissance.", "cohérent ou réserves",
     "FNB diversifié, la part technologique reste à vérifier"),
]


def conforme_attendu(verdict, attendu):
    v = (verdict or "").lower()
    morceaux = [a.strip() for a in attendu.split(" ou ")]
    synonymes = {"réserves": "cohérent avec réserves"}
    return any(v == synonymes.get(m, m) for m in morceaux)


def main():
    dossier = Path(__file__).resolve().parent
    if charger_identifiants_fichier(dossier):
        print("Identifiants AWS lus dans identifiants_aws.txt")
    else:
        print("ATTENTION : identifiants_aws.txt introuvable ou incomplet dans", dossier)
    ka = SecondAvis(dossier)
    lignes = []
    for i, (persona, demande, attendu, objet) in enumerate(SCENARIOS, 1):
        print(f"\n[{i}/{len(SCENARIOS)}] {PERSONAS[persona]['nom']} : {demande}")
        try:
            r = ka.demander(persona, demande)
            a = r["avis"] or {}
            ctrl = r["controles"]
            renvois = sum(1 for e in r["trace"]["etapes"] if e["type"] == "controle" and any(not c["ok"] for c in e["controles"]))
            lignes.append({"n": i, "profil": PERSONAS[persona]["nom"], "demande": demande, "attendu": attendu, "objet": objet,
                           "obtenu": a.get("verdict", "aucun avis"), "ok": conforme_attendu(a.get("verdict"), attendu),
                           "controles": f"{sum(c['ok'] for c in ctrl)}/{len(ctrl)}", "renvois": renvois,
                           "appels": len(r["appels"]), "duree": r["trace"]["duree_totale_s"],
                           "trace": Path(r["fichier_trace"]).name, "resume": a.get("resume", "")})
        except Exception as e:
            import traceback
            print(f"  ÉCHEC : {type(e).__name__} : {e}")
            traceback.print_exc()
            lignes.append({"n": i, "profil": PERSONAS[persona]["nom"], "demande": demande, "attendu": attendu, "objet": objet,
                           "obtenu": f"erreur ({type(e).__name__})", "ok": False, "controles": "n.d.", "renvois": "n.d.",
                           "appels": "n.d.", "duree": "n.d.", "trace": "", "resume": ""})
            if "Expired" in str(e) or "credentials" in str(e).lower():
                print("  Identifiants AWS absents ou expirés : arrêt.")
                break

    ok = sum(l["ok"] for l in lignes)
    texte = [f"# Résultats des tests de validation\n",
             f"Exécutés le {datetime.now():%Y-%m-%d à %H:%M} avec le modèle {ka.modele} sur Amazon Bedrock (us-east-1). "
             f"Script : `lancer_tests.py`. **{ok} verdict(s) conforme(s) à l'attendu sur {len(lignes)}.**\n",
             "| # | Profil | Demande | Attendu | Obtenu | Conforme | Contrôles | Renvois au modèle | Calculs | Durée (s) | Trace |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for l in lignes:
        texte.append(f"| {l['n']} | {l['profil']} | {l['demande']} | {l['attendu']} | {l['obtenu']} | {'oui' if l['ok'] else 'non'} | "
                     f"{l['controles']} | {l['renvois']} | {l['appels']} | {l['duree']} | `{l['trace']}` |")
    texte.append("\n## Objet de chaque test et résumé de l'avis\n")
    for l in lignes:
        texte.append(f"**{l['n']}. {l['profil']}** : {l['objet']}.  \n> {l['resume']}\n")
    sortie = Path(__file__).resolve().parent / "docs" / "tests_resultats.md"
    sortie.parent.mkdir(exist_ok=True)
    sortie.write_text("\n".join(texte), encoding="utf-8")
    print(f"\n{ok}/{len(lignes)} verdicts conformes. Résultats écrits dans {sortie}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

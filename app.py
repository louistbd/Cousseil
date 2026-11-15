"""Cousseil : le coussin de sécurité d'une décision d'investissement, pour dormir sur ses deux oreilles.

Application Streamlit. Datathon PolyFinances 2026, défi AlphaForge AI.
Lancer : python -m streamlit run app.py
Simulation pédagogique : profils fictifs, aucun conseil financier personnalisé.
"""

import os
import base64
import html
import json
import re
from pathlib import Path

import pandas as pd
import streamlit as st

import second_avis as moteur_mod
from second_avis import charger_identifiants_fichier, COULEURS, DESCRIPTION_REGLES, METHODE, NOMS_COURTS, NOMS_OUTILS, PERSONAS, SOURCES, SecondAvis

NOM = "Cousseil"
DOSSIER = Path(__file__).resolve().parent
TRACES = DOSSIER / "traces"

ASSETS = DOSSIER / "assets"
LOGO_SVG = (ASSETS / "logo.svg").read_text(encoding="utf-8") if (ASSETS / "logo.svg").exists() else ""
st.set_page_config(page_title=f"{NOM} : analyse d'une décision d'investissement", layout="wide",
                   page_icon=str(ASSETS / "logo.png") if (ASSETS / "logo.png").exists() else None)


def logo(taille):
    return LOGO_SVG.replace('width="64" height="64"', f'width="{taille}" height="{taille}"')
IDS_FICHIER = charger_identifiants_fichier(DOSSIER)


def charger_secrets():
    """Version en ligne (Streamlit Community Cloud) : identifiants AWS lus dans les secrets de l'hébergeur, jamais dans le dépôt."""
    try:
        s = st.secrets
        if "AWS_ACCESS_KEY_ID" not in s or "AWS_SECRET_ACCESS_KEY" not in s:
            return False
        for k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
            if k in s:
                os.environ[k] = str(s[k])
        os.environ.setdefault("AWS_DEFAULT_REGION", moteur_mod.REGION)
        return True
    except Exception:
        return False


IDS_SECRETS = charger_secrets()
ACCES_AWS = IDS_FICHIER or IDS_SECRETS or bool(os.environ.get("AWS_ACCESS_KEY_ID"))

EXEMPLES = {
    "robert": [("Tesla, 25 %", "Tesla est partout dans les nouvelles, je veux y mettre 25 % de mon épargne."),
               ("Palantir, 5 %", "Je veux acheter 5 % de Palantir, tout le monde en parle."),
               ("Bitcoin, 20 %", "Je pense mettre 20 % de mon portefeuille en Bitcoin.")],
    "amira": [("Tout en IA et crypto", "Je suis jeune, je veux tout mettre dans l'IA et la crypto : NVIDIA, Bitcoin et Ether."),
              ("Tesla, 25 %", "Tesla est partout dans les nouvelles, je veux y mettre 25 % de mon épargne."),
              ("QQQ, +10 %", "J'aimerais ajouter 10 % de QQQ pour plus de croissance.")],
    "mateo": [("Exxon Mobil, 8 %", "Exxon a très bien performé, je pense ajouter 8 % d'Exxon Mobil à mon portefeuille."),
              ("Enbridge, 10 %", "Je veux ajouter 10 % d'Enbridge pour les dividendes."),
              ("Microsoft, +5 %", "Je voudrais 5 % de Microsoft en plus, c'est une entreprise solide.")],
}
LIBELLES_VERDICT = {"cohérent": "Cohérent avec le profil", "cohérent avec réserves": "Cohérent, avec réserves",
                    "incohérent": "Incohérent avec le profil", "impossible à évaluer": "Impossible à évaluer"}

# ---------------------------------------------------------------------------
# Styles communs
# ---------------------------------------------------------------------------

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
.stApp, .stApp p, .stApp li, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp textarea, .stApp input, .stApp td, .stApp div, .stApp th {font-family: 'Inter', -apple-system, 'Segoe UI', sans-serif;}
[data-testid="stSidebar"] .stMarkdown p, [data-testid="stSidebar"] .stMarkdown li {font-size:14.5px; line-height:1.5}
[data-testid="stMetricValue"] {font-weight:600; letter-spacing:-0.02em; color:#101828}
footer {visibility: hidden;}
[data-testid="stDecoration"] {display:none;}
header[data-testid="stHeader"] {background: transparent;}
[data-testid="stSidebar"] {background:#f4f6f9; border-right:1px solid #e4e7ec;}
.marque {display:flex; align-items:center; gap:12px;}
.marque .mot {font-size:30px; font-weight:700; color:#17375e; letter-spacing:-0.025em; line-height:1}
.marque .slogan {font-size:14.5px; color:#475467; margin-top:4px}
.marque .equipe {font-size:12.5px; color:#17375e; font-weight:500; margin-top:3px}
.badge-evt {font-size:12px; color:#17375e; background:#eef2f7; border:1px solid #dbe3ee; border-radius:999px; padding:5px 12px; white-space:nowrap}
.atouts {display:grid; grid-template-columns:repeat(3, 1fr); gap:12px; margin:16px 0 8px}
.atout {background:linear-gradient(180deg,#f8fafc,#f2f5f9); border:1px solid #e4e7ec; border-radius:12px; padding:12px 14px}
.atout b {display:block; color:#17375e; font-size:14px; margin-bottom:2px}
.atout span {color:#475467; font-size:13px; line-height:1.4}
@media (max-width: 760px) {.atouts {grid-template-columns:1fr} .badge-evt {display:none}}
[data-testid="stMetric"] {background:#fff; border:1px solid #e4e7ec; border-radius:12px; padding:12px 16px; box-shadow:0 1px 2px rgba(16,24,40,.04)}
[data-testid="stMetricLabel"] p {font-size:12.5px !important; color:#475467 !important}
.stButton > button {border-radius:8px; font-weight:500}
.stButton > button[kind="primary"] {background:#17375e; border-color:#17375e; padding:0.5rem 1.4rem}
.stButton > button[kind="primary"]:hover {background:#1f5f8b; border-color:#1f5f8b}
.stButton > button[kind="primary"]:disabled {background:#c9d3df; border-color:#c9d3df; color:#ffffff}
[data-testid="stTextArea"] textarea {border-radius:10px}
.stTabs [data-baseweb="tab-list"] {gap:22px; border-bottom:1px solid #e4e7ec}
.stTabs [data-baseweb="tab"] {font-weight:500; padding:10px 2px}
[data-testid="stExpander"] details {border-radius:10px; border-color:#e4e7ec; background:#fff}
.pied-produit {margin-top:48px; padding-top:14px; border-top:1px solid #e4e7ec; display:flex; flex-wrap:wrap; gap:8px 18px; align-items:center; font-size:12.5px; color:#667085}
[data-testid="stSidebarCollapsedControl"], [data-testid="stExpandSidebarButton"] {visibility: visible !important; opacity: 1 !important;}
.block-container {padding: 2.6rem 3rem 2rem 3rem; max-width: none;}
@media (min-width: 1600px) {.block-container {padding-left: 4rem; padding-right: 4rem;}}
@media (max-width: 640px) {.block-container {padding-top: 3.5rem;} .entete-produit .nom {font-size:24px}}
h1, h2, h3, h4 {letter-spacing: -0.01em; color: #101828;}
.entete-produit {display:flex; flex-wrap:wrap; align-items:baseline; column-gap:14px; border-bottom:1px solid #e4e7ec; padding-bottom:10px; margin-bottom:6px}
.entete-produit .nom {font-size:28px; font-weight:700; color:#1f3a5f}
.entete-produit .role {font-size:15px; color:#475467}
.mention {font-size:12.5px; color:#667085}
.verdict {display:inline-block; color:#fff; padding:5px 14px; border-radius:999px; font-weight:600; font-size:15px}
.resume {font-size:17px; line-height:1.5; color:#101828; margin:10px 0 4px}
.section {font-size:13px; font-weight:600; text-transform:uppercase; letter-spacing:.04em; color:#475467; margin:22px 0 6px}
table.tb {border-collapse:collapse; width:100%; font-size:14px}
table.tb th {text-align:left; font-weight:600; color:#475467; border-bottom:1px solid #d0d5dd; padding:6px 8px; font-size:12.5px}
table.tb td {border-bottom:1px solid #eaecf0; padding:6px 8px; vertical-align:top}
table.tb td.n, table.tb th.n {text-align:right; font-variant-numeric: tabular-nums; white-space:nowrap}
table.tb tr.fort td {font-weight:600}
.tb-cadre {width:100%; overflow-x:auto}
table.tb.fixe {table-layout:fixed}
table.tb.fixe td {white-space:normal; overflow-wrap:anywhere}
.ecart {color:#b42318}
.ok {color:#027a48}
.panneau {border-left:3px solid #1f5f8b; background:#f5f8fb; padding:12px 16px; margin:8px 0; border-radius:0 10px 10px 0}
.vide {color:#667085; border:1px dashed #d0d5dd; border-radius:12px; padding:22px; text-align:center; background:#fafbfc}
</style>""", unsafe_allow_html=True)


def e(x):
    return html.escape(str(x))


def de(nom):
    return f"d'{nom}" if nom[:1].lower() in "aeiouyh" else f"de {nom}"


def unite(regle, v):
    if not isinstance(v, (int, float)):
        return str(v)
    return f"{v} positions" if regle == "lignes_min" else f"{v:.1f} %".replace(".", ",").replace("-", "−")


def nombre(x, unite=" %", signe=False):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "n.d."
    texte = f"{x:+.1f}" if signe else f"{x:.1f}"
    return texte.replace(".", ",").replace("-", "−") + unite


def tableau(colonnes, lignes, numeriques=(), fortes=(), largeurs=None):
    """Tableau HTML : colonnes numériques alignées à droite, valeurs déjà formatées.
    largeurs : liste de pourcentages pour fixer la largeur des colonnes (évite les débordements)."""
    cols = "".join(f"<col style='width:{w}%'>" for w in largeurs) if largeurs else ""
    tete = "".join(f"<th class='{'n' if c in numeriques else ''}'>{e(c)}</th>" for c in colonnes)
    corps = ""
    for i, l in enumerate(lignes):
        cellules = "".join(f"<td class='{'n' if c in numeriques else ''}'>{l.get(c, '')}</td>" for c in colonnes)
        corps += f"<tr class='{'fort' if i in fortes else ''}'>{cellules}</tr>"
    classe = "tb fixe" if largeurs else "tb"
    st.markdown(f"<div class='tb-cadre'><table class='{classe}'><colgroup>{cols}</colgroup><tr>{tete}</tr>{corps}</table></div>",
                unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Connexion AWS
# ---------------------------------------------------------------------------

def lire_identifiants(texte):
    """Lit le bloc « Get AWS CLI credentials » de Workshop Studio, quel que soit l'onglet copié."""
    valeurs = {}
    for cle in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        m = re.search(cle + r"""\s*[=:]\s*["']?([^"'\s]+)""", texte, re.IGNORECASE)
        if m:
            valeurs[cle] = m.group(1)
    return valeurs


@st.cache_resource(show_spinner="Chargement des données de marché")
def creer_moteur(cle, secret, jeton):
    import boto3
    if cle and secret:
        session = boto3.session.Session(aws_access_key_id=cle, aws_secret_access_key=secret,
                                        aws_session_token=jeton or None, region_name=moteur_mod.REGION)
    else:
        session = boto3.session.Session(region_name=moteur_mod.REGION)
    return SecondAvis(DOSSIER, client=session.client("bedrock-runtime", config=moteur_mod.CONFIG_CLIENT())), session


def recuperation(v):
    if "recuperation_semaines" not in v:
        return "n.d."
    s = v["recuperation_semaines"]
    if s is None:
        return "pas encore"
    annees = f"{s / 52:.1f}".replace(".", ",")
    return f"{s} sem. ({annees} an)" if s >= 52 else f"{s} sem."


def source_risque(v):
    t, part = (v.get("principal_risque") or [None, None])[:2]
    if not t:
        return "n.d."
    return f"{e(t)} : {nombre(part)} du risque"


def message_erreur(err):
    texte = str(err)
    if any(x in texte for x in ("ExpiredToken", "expired", "NoCredentials", "Unable to locate credentials",
                                "UnrecognizedClient", "InvalidClientTokenId", "security token")):
        return ("La connexion à Amazon Bedrock a échoué : identifiants AWS absents ou expirés. "
                "Copiez de nouveau le bloc « Get AWS CLI credentials » depuis Workshop Studio et collez-le dans "
                "« Connexion AWS ». Vous pouvez aussi consulter une analyse enregistrée.")
    if "AccessDenied" in texte:
        return "Amazon Bedrock a refusé l'appel (AccessDenied). Vérifiez que la région est us-east-1 et que le modèle est activé."
    return f"L'analyse s'est interrompue : {type(err).__name__}. Détail : {texte[:300]}"


# ---------------------------------------------------------------------------
# Affichage d'un résultat
# ---------------------------------------------------------------------------

def lignes_comparatif(r):
    return {l["portefeuille"]: l for l in (r.get("comparatif") or {}).get("lignes", [])}


def afficher_resultat(r, compact=False):
    a = r.get("avis") or {}
    ctrl = r.get("controles", [])
    n_ok = sum(c["ok"] for c in ctrl)
    t = r.get("trace", {})
    verdict = a.get("verdict", "impossible à évaluer")
    comp = lignes_comparatif(r)

    st.markdown(f"<span class='verdict' style='background:{COULEURS.get(verdict, '#475467')}'>"
                f"{e(LIBELLES_VERDICT.get(verdict, verdict))}</span>", unsafe_allow_html=True)
    st.markdown(f"<div class='resume'>{e(a.get('resume', ''))}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='mention'>{n_ok} contrôle(s) de cohérence sur {len(ctrl)} réussis · "
                f"{len(r.get('appels', {}))} calculs · {t.get('duree_totale_s', 'n.d.')} s · demande : « {e(r['demande'])} »</div>",
                unsafe_allow_html=True)

    if "Actuel" in comp:
        ref = comp["Actuel"]
        cible = comp.get("Demande") or comp.get("Alternative")
        nom_cible = "demande" if "Demande" in comp else "alternative"
        cols = st.columns(4)
        for col, (titre, cle) in zip(cols, [("Volatilité annuelle", "volatilite_annualisee_pct"),
                                            ("Pire baisse historique", "perte_maximale_pct"),
                                            ("Résultat en 2022", "rendement_2022_pct"),
                                            ("Rendement annualisé", "rendement_annualise_pct")]):
            if cible:
                delta = cible[cle] - ref[cle]
                col.metric(f"{titre} ({nom_cible})", nombre(cible[cle]), f"{delta:+.1f} pt vs actuel".replace(".", ","),
                           delta_color="inverse" if cle == "volatilite_annualisee_pct" else "normal")
            else:
                col.metric(f"{titre} (actuel)", nombre(ref[cle]))

    if compact:
        if comp:
            tableau(["Portefeuille", "Volatilité", "Pire baisse", "Règles"],
                    [{"Portefeuille": e(k), "Volatilité": nombre(v["volatilite_annualisee_pct"]),
                      "Pire baisse": nombre(v["perte_maximale_pct"]), "Règles": e(v["regles_respectees"])}
                     for k, v in comp.items()], numeriques=("Volatilité", "Pire baisse", "Règles"))
        return

    graphe = (r.get("comparatif") or {}).get("graphique_png")
    if graphe:
        st.markdown("<div class='section'>Évolution simulée de 100 $ investis</div>", unsafe_allow_html=True)
        st.image(base64.b64decode(graphe), use_container_width=True)
    if comp:
        tableau(["Portefeuille", "Rendement annualisé", "Volatilité", "Pire baisse", "Retour au sommet", "2022",
                 "Principale source de risque", "Règles du profil", "Règles non respectées"],
                [{"Portefeuille": e(k), "Rendement annualisé": nombre(v["rendement_annualise_pct"]),
                  "Volatilité": nombre(v["volatilite_annualisee_pct"]), "Pire baisse": nombre(v["perte_maximale_pct"]),
                  "Retour au sommet": recuperation(v), "Principale source de risque": source_risque(v),
                  "2022": nombre(v["rendement_2022_pct"]), "Règles du profil": e(v["regles_respectees"]),
                  "Règles non respectées": f"<span class='ecart'>{e(', '.join(v['ecarts']))}</span>" if v["ecarts"] else "<span class='ok'>aucune</span>"}
                 for k, v in comp.items()],
                numeriques=("Rendement annualisé", "Volatilité", "Pire baisse", "2022", "Règles du profil"))
        st.markdown(f"<div class='mention'>Chiffres historiques en CAD, {e(r.get('periode', ''))}, portefeuilles rééquilibrés "
                    "chaque semaine. « Retour au sommet » : semaines nécessaires pour effacer la pire baisse. « Principale "
                    "source de risque » : position qui porte la plus grande part de la variance du portefeuille. Ils décrivent le passé et ne prédisent pas les rendements futurs. Les règles sont des "
                    "hypothèses de l'équipe.</div>", unsafe_allow_html=True)

    st.markdown("<div class='section'>Ce qui fonde l'avis</div>", unsafe_allow_html=True)
    faits = a.get("faits", [])
    if faits:
        tableau(["Constat", "Valeur", "Calcul source"],
                [{"Constat": e(f.get("affirmation")), "Valeur": f"<b>{e(f.get('valeur'))}</b>",
                  "Calcul source": e(f"{f.get('id_appel')} · {NOMS_OUTILS.get(r['appels'].get(f.get('id_appel'), {}).get('outil'), 'introuvable')}")}
                 for f in faits], largeurs=[58, 20, 22])
    if a.get("tensions_avec_profil"):
        st.markdown("<div class='section'>Écarts avec le profil</div>", unsafe_allow_html=True)
        st.markdown("<div class='panneau' style='border-left-color:#b54708;background:#fffaf5'><ul style='margin:0;padding-left:18px'>"
                    + "".join(f"<li style='margin:2px 0'>{e(x)}</li>" for x in a["tensions_avec_profil"]) + "</ul></div>",
                    unsafe_allow_html=True)

    alt = a.get("alternative")
    if alt:
        st.markdown("<div class='section'>Alternative vérifiée</div>", unsafe_allow_html=True)
        compo = " · ".join(f"{e(x['symbole'])} {nombre(x['poids_pct'], ' %').replace(',0 %', ' %')}" for x in alt.get("positions", []))
        st.markdown(f"<div class='panneau'>{e(alt.get('description'))}<br><span class='mention'>Composition : {compo}. "
                    f"Vérifiée par le calcul {e(alt.get('id_appel_verification'))}.</span></div>", unsafe_allow_html=True)

    with st.expander("Hypothèses et limites"):
        st.markdown("**Hypothèses**\n" + "\n".join(f"- {x}" for x in a.get("hypotheses", [])))
        st.markdown("**Limites et incertitudes**\n" + "\n".join(f"- {x}" for x in a.get("limites", [])))
    with st.expander(f"Contrôles de cohérence ({n_ok}/{len(ctrl)})"):
        st.caption("Avant d'être affiché, l'avis est comparé aux calculs : chaque chiffre doit apparaître dans le calcul cité, "
                   "et une alternative doit avoir été vérifiée. En cas d'écart, l'avis est renvoyé au modèle.")
        tableau(["Résultat", "Contrôle", "Détail"],
                [{"Résultat": "<span class='ok'>réussi</span>" if c["ok"] else "<span class='ecart'>échec</span>",
                  "Contrôle": e(c["controle"]), "Détail": e(c["detail"])} for c in ctrl])
        renvois = [x for x in t.get("etapes", []) if x["type"] == "controle" and any(not c["ok"] for c in x["controles"])]
        if renvois:
            st.markdown(f"<div class='section'>Renvois au modèle avant acceptation : {len(renvois)}</div>", unsafe_allow_html=True)
            for k, x in enumerate(renvois, 1):
                tableau(["Renvoi", "Écart détecté", "Détail"],
                        [{"Renvoi": str(k), "Écart détecté": e(c["controle"]), "Détail": f"<span class='ecart'>{e(c['detail'])}</span>"}
                         for c in x["controles"] if not c["ok"]], largeurs=[10, 60, 30])
    with st.expander("Trace d'exécution"):
        st.caption(f"Modèle {t.get('modele')} sur Amazon Bedrock (us-east-1) · "
                   f"{t.get('jetons', {}).get('entree', 0)} jetons en entrée, {t.get('jetons', {}).get('sortie', 0)} en sortie.")
        for x in t.get("etapes", []):
            if x["type"] == "outil":
                st.markdown(f"**{x['id_appel']}** · {NOMS_OUTILS.get(x['outil'], x['outil'])} · `{json.dumps(x['entree'], ensure_ascii=False)[:180]}`")
            elif x["type"] == "controle":
                ko = sum(not c["ok"] for c in x["controles"])
                st.markdown(f"Contrôle de cohérence : {'renvoi au modèle, ' + str(ko) + ' écart(s)' if ko else 'avis accepté'}")
            else:
                st.markdown(f"Appel au modèle · {x.get('duree_s')} s · requête `{x.get('request_id')}`")
        st.download_button("Télécharger la trace complète (JSON)", json.dumps(r, ensure_ascii=False, indent=2, default=str),
                           file_name=Path(r.get("fichier_trace", "trace.json")).name, mime="application/json")


# ---------------------------------------------------------------------------
# Barre latérale : profil, connexion, source
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown(f"<div class='marque' style='margin:-6px 0 20px'>{logo(44)}</div>",
                unsafe_allow_html=True)
    st.markdown("### Profil de l'investisseur")
    persona = st.radio("Profil", list(PERSONAS), label_visibility="collapsed",
                       format_func=lambda k: f"{PERSONAS[k]['nom']}, {PERSONAS[k]['age']} ans · risque {PERSONAS[k]['profil_risque']}")
    p = PERSONAS[persona]
    st.markdown(f"{e(p['situation'])}. Horizon de placement : **{e(p['horizon'])}**. Objectif : {e(p['objectif'].lower())}.")
    st.markdown("\n".join(f"- {x}" for x in p["preferences"]))
    with st.expander("Portefeuille de départ et règles"):
        st.caption("Portefeuille fictif et seuils fixés par l'équipe pour la simulation.")
        tableau(["Actif", "Poids"], [{"Actif": e(k), "Poids": f"{v} %"} for k, v in p["portefeuille_actuel"].items()], numeriques=("Poids",))
        st.markdown("\n".join(f"- {DESCRIPTION_REGLES[k]} : **{'oui' if k == 'esg' else str(v).replace('.', ',') + (' positions' if k == 'lignes_min' else ' %')}**"
                              for k, v in p["regles"].items()))

    st.markdown("### Source de l'analyse")
    source = st.radio("Source", ["Nouvelle analyse", "Analyse enregistrée"], label_visibility="collapsed", index=0 if ACCES_AWS else 1,
                      help="« Analyse enregistrée » réaffiche une analyse du dossier traces/ sans appeler AWS.")

    titre_aws = "Connexion AWS · active" if ACCES_AWS else "Connexion AWS · à configurer"
    with st.expander(titre_aws, expanded=False):
        if ACCES_AWS:
            st.markdown(f"<div class='mention'><span class='ok'>Identifiants lus dans <b>{'les secrets de l’hébergeur' if IDS_SECRETS else 'identifiants_aws.txt'}</b>.</span> "
                        "Rien à faire. Pour en utiliser d'autres, collez-les ci-dessous.</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='mention'>Pour lancer une nouvelle analyse, collez le bloc « Get AWS CLI credentials » "
                        "(Workshop Studio) ci-dessous ou dans le fichier identifiants_aws.txt. Les clés restent en mémoire. "
                        "Sans accès AWS, choisissez « Analyse enregistrée » pour consulter les analyses déjà réalisées.</div>",
                        unsafe_allow_html=True)
        bloc = st.text_area("Identifiants AWS temporaires", height=90, placeholder="set AWS_ACCESS_KEY_ID=…")
        ids = lire_identifiants(bloc) if bloc else {}
        moteur, session = creer_moteur(ids.get("AWS_ACCESS_KEY_ID"), ids.get("AWS_SECRET_ACCESS_KEY"), ids.get("AWS_SESSION_TOKEN"))
        if st.button("Vérifier la connexion"):
            try:
                compte = session.client("sts").get_caller_identity()["Account"]
                st.success(f"Connecté au compte AWS se terminant par {compte[-4:]}, région us-east-1.")
            except Exception as err:
                st.error(message_erreur(err))

    st.markdown("<div class='mention'><b>Équipe :</b> Louis Thibaudat, Nathan Marie et Virgile Rosin.<br>Projet réalisé lors du Datathon PolyFinances (Polytechnique Montréal), "
                "14-15 novembre 2026, défi AlphaForge AI proposé par Banque Nationale et AWS. Simulation pédagogique : "
                "profils et portefeuilles fictifs, aucun conseil financier personnalisé.</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# En-tête
# ---------------------------------------------------------------------------

st.markdown(f"<div class='entete-produit' style='align-items:center'><div class='marque'><div>"
            f"<div class='mot'>{NOM}</div>"
            "<div class='slogan'>Le coussin de sécurité d'une décision d'investissement, pour dormir sur ses deux oreilles</div><div class='equipe'>Par Louis Thibaudat, Nathan Marie et Virgile Rosin</div></div></div>"
            "<span class='badge-evt' style='margin-left:auto'>Datathon PolyFinances · 14-15 novembre 2026</span></div>",
            unsafe_allow_html=True)
st.markdown("<div class='atouts'>"
            "<div class='atout'><b>Avant de décider</b><span>La demande est simulée sur le portefeuille et confrontée au profil de l'investisseur.</span></div>"
            "<div class='atout'><b>Chaque chiffre est vérifiable</b><span>Les calculs sont faits en Python ; un contrôle relie chaque chiffre de l'avis à sa source.</span></div>"
            "<div class='atout'><b>Une alternative concrète</b><span>Si la demande ne convient pas, une option qui respecte le profil est proposée et vérifiée.</span></div>"
            "</div>", unsafe_allow_html=True)

ong_analyse, ong_comparer, ong_sensib, ong_donnees, ong_methode = st.tabs(
    ["Analyse", "Comparer les profils", "Sensibilité", "Données et sources", "Méthode"])

# ---------------------------------------------------------------------------
# Onglet Analyse
# ---------------------------------------------------------------------------

with ong_analyse:
    if source == "Nouvelle analyse":
        st.markdown(f"#### Demande {de(p['nom'])}")
        cols = st.columns([0.55] + [1] * len(EXEMPLES[persona]))
        cols[0].markdown("<div class='mention' style='padding-top:8px'>Exemples :</div>", unsafe_allow_html=True)
        for i, (court, long) in enumerate(EXEMPLES[persona]):
            if cols[i + 1].button(court, key=f"ex_{persona}_{i}", use_container_width=True):
                st.session_state[f"demande_{persona}"] = long
        demande = st.text_area("Demande de l'investisseur", key=f"demande_{persona}", height=80, label_visibility="collapsed",
                               placeholder="Par exemple : je veux mettre 25 % de mon épargne sur Tesla.")
        lancer = st.button("Analyser la demande", type="primary", disabled=not (demande or "").strip())
        if lancer:
            erreur = None
            with st.status("Analyse en cours, généralement 30 à 90 secondes", expanded=True) as statut:
                try:
                    r = moteur.demander(persona, demande, verbose=False, suivi=statut.write)
                    st.session_state[f"resultat_{persona}"] = r
                    statut.update(label="Analyse terminée", state="complete", expanded=False)
                except Exception as err:
                    erreur = err
                    statut.update(label="Analyse interrompue", state="error", expanded=False)
            if erreur is not None:
                st.error(message_erreur(erreur))
        if f"resultat_{persona}" in st.session_state:
            st.divider()
            afficher_resultat(st.session_state[f"resultat_{persona}"])
        elif not lancer:
            st.markdown("<div class='vide'>Aucune analyse pour ce profil. Choisissez un exemple ou rédigez une demande, "
                        "puis lancez l'analyse.</div>", unsafe_allow_html=True)
    else:
        fichiers = sorted(TRACES.glob(f"avis_{persona}_*.json"), reverse=True) if TRACES.exists() else []
        if not fichiers:
            st.markdown(f"<div class='vide'>Aucune analyse enregistrée pour {e(p['nom'])}. Les analyses lancées en mode « Nouvelle analyse » "
                        "sont conservées automatiquement dans le dossier traces/.</div>", unsafe_allow_html=True)
        else:
            def etiquette(f):
                try:
                    d = json.loads(f.read_text(encoding="utf-8"))
                    return f"{PERSONAS.get(d['persona'], {}).get('nom', d['persona'])} · {d['demande'][:70]} · {d['trace']['id']}"
                except Exception:
                    return f.name
            if not ACCES_AWS:
                st.markdown("<div class='panneau'>Version de démonstration en ligne : chaque analyse ci-dessous a été produite "
                            "par le modèle Claude sur Amazon Bedrock pendant le Datathon et enregistrée avec sa trace complète. "
                            "« Rejouer le déroulé » montre les étapes de l'agent une à une : les réponses du modèle viennent de la "
                            "trace, les calculs sont refaits en direct.</div>", unsafe_allow_html=True)
            choix = st.selectbox("Analyse enregistrée", fichiers, format_func=etiquette)
            r = json.loads(choix.read_text(encoding="utf-8"))
            if st.button("Rejouer le déroulé de cette analyse", help="Relecture d'une analyse réelle : réponses du modèle issues de la trace, calculs refaits."):
                from rejeu import ClientRejeu
                with st.status("Relecture d'une analyse réelle (Amazon Bedrock), en accéléré", expanded=True) as statut:
                    try:
                        c = ClientRejeu(DOSSIER, vitesse=0.25); c.choisir(str(choix))
                        r2 = SecondAvis(DOSSIER, client=c).demander(r["persona"], r["demande"], verbose=False, suivi=statut.write)
                        try:
                            Path(r2.get("fichier_trace", "")).unlink()
                        except Exception:
                            pass
                        r = r2
                        statut.update(label="Relecture terminée", state="complete", expanded=False)
                    except Exception as err:
                        statut.update(label="Relecture interrompue", state="error", expanded=False)
                        st.error(message_erreur(err))
            st.session_state[f"resultat_{r['persona']}"] = r
            afficher_resultat(r)

# ---------------------------------------------------------------------------
# Onglet Comparer
# ---------------------------------------------------------------------------

with ong_comparer:
    st.markdown("#### La même demande pour les trois profils")
    st.markdown("<div class='mention'>Une même demande peut convenir à un profil et pas à un autre. Les trois analyses sont "
                "lancées l'une après l'autre (environ 3 minutes).</div>", unsafe_allow_html=True)
    demande_c = st.text_input("Demande commune", value="Tesla est partout dans les nouvelles, je veux y mettre 25 % de mon épargne.")
    if st.button("Analyser pour les trois profils", type="primary", disabled=source != "Nouvelle analyse"):
        resultats, erreur = {}, None
        with st.status("Trois analyses en cours", expanded=True) as statut:
            try:
                for k in PERSONAS:
                    statut.write(f"Profil {PERSONAS[k]['nom']}")
                    resultats[k] = moteur.demander(k, demande_c, verbose=False, suivi=statut.write)
                statut.update(label="Comparaison terminée", state="complete", expanded=False)
            except Exception as err:
                erreur = err
                statut.update(label="Comparaison interrompue", state="error", expanded=False)
        if erreur is not None:
            st.error(message_erreur(erreur))
        st.session_state["comparaison"] = resultats
    if st.session_state.get("comparaison"):
        cols = st.columns(3, gap="large")
        for col, (k, r) in zip(cols, st.session_state["comparaison"].items()):
            with col:
                st.markdown(f"**{PERSONAS[k]['nom']}** · risque {PERSONAS[k]['profil_risque']} · {PERSONAS[k]['horizon']}")
                afficher_resultat(r, compact=True)
    else:
        st.markdown("<div class='vide'>Lancez l'analyse pour voir les trois avis côte à côte.</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Onglet Sensibilité
# ---------------------------------------------------------------------------

with ong_sensib:
    st.markdown(f"#### Le verdict dépend-il du réglage des seuils ? Profil {de(p['nom'])}")
    st.markdown("<div class='mention'>Les seuils des règles sont des hypothèses. On les rend plus stricts (×0,75) ou plus souples "
                "(×1,25 et ×1,5) pour voir si la conclusion change. Une exclusion totale (crypto à 0 %) et la règle ESG "
                "restent inchangées.</div>", unsafe_allow_html=True)
    r = st.session_state.get(f"resultat_{persona}")
    comp = lignes_comparatif(r) if r else {}
    portefeuilles = {}
    if r:
        for a_ in r.get("appels", {}).values():
            if a_["outil"] == "simuler_modification" and "apres" in a_["sortie"]:
                portefeuilles.setdefault("Demande", a_["sortie"]["apres"]["poids_pct"])
        alt = (r.get("avis") or {}).get("alternative") or {}
        if "Demande" not in portefeuilles:
            for k_, a_ in r.get("appels", {}).items():
                if a_["outil"] == "evaluer_portefeuille" and "contraintes" in a_["sortie"] and k_ != alt.get("id_appel_verification") \
                        and a_["sortie"]["contraintes"]["statut"] != "conforme":
                    portefeuilles["Demande"] = a_["sortie"]["poids_pct"]
                    break
        if alt.get("positions"):
            portefeuilles["Alternative"] = {x["symbole"]: x["poids_pct"] for x in alt["positions"]}
    if not portefeuilles:
        st.markdown(f"<div class='vide'>Lancez d'abord une analyse pour {e(p['nom'])} dans l'onglet « Analyse ». "
                    "La sensibilité s'applique au portefeuille demandé et à l'alternative proposée.</div>", unsafe_allow_html=True)
    else:
        facteurs = (0.75, 1.0, 1.25, 1.5)
        noms_f = {0.75: "Seuils ×0,75 (plus stricts)", 1.0: "Seuils de référence", 1.25: "Seuils ×1,25", 1.5: "Seuils ×1,5 (plus souples)"}
        res = {nom: moteur.sensibilite(persona, poids, facteurs) for nom, poids in portefeuilles.items()}
        lignes = []
        for i, f in enumerate(facteurs):
            ligne = {"Réglage": noms_f[f]}
            for nom in res:
                l = res[nom]["lignes"][i]
                ligne[nom] = (f"<span class='{'ok' if l['statut'] == 'conforme' else 'ecart'}'>{l['respectees']}/{l['total']} règles</span>")
            lignes.append(ligne)
        tableau(["Réglage"] + list(res), lignes, numeriques=tuple(res), fortes=(1,))
        for nom, rr in res.items():
            statuts = [l["statut"] for l in rr["lignes"]]
            if len(set(statuts)) == 1:
                st.markdown(f"- **{nom}** : même conclusion pour tous les réglages testés ({statuts[0]}). "
                            "Le verdict ne dépend pas d'un réglage fin des seuils.")
            else:
                bascule = [noms_f[f].lower() for f, s_ in zip(facteurs, statuts) if s_ != statuts[1]]
                st.markdown(f"- **{nom}** : la conclusion change avec {', '.join(bascule)}. Elle dépend du niveau de seuil choisi : à présenter avec prudence.")
        nom_detail = "Demande" if "Demande" in res else list(res)[0]
        st.markdown(f"<div class='section'>Détail des règles au réglage de référence ({e(nom_detail.lower())})</div>", unsafe_allow_html=True)
        tableau(["Règle", "Valeur", "Seuil", "Respectée"],
                [{"Règle": e(DESCRIPTION_REGLES[x["regle"]]), "Valeur": e(unite(x["regle"], x["valeur"])),
                  "Seuil": e(unite(x["regle"], x["seuil"])),
                  "Respectée": "<span class='ok'>oui</span>" if x["respectee"] else "<span class='ecart'>non</span>"}
                 for x in res[nom_detail]["detail"]], numeriques=("Valeur", "Seuil"))

# ---------------------------------------------------------------------------
# Onglet Données et sources
# ---------------------------------------------------------------------------

with ong_donnees:
    st.markdown("#### Contrôles de qualité des données")
    ctrl_d = moteur.donnees.controles()
    tableau(["Résultat", "Contrôle", "Constat"],
            [{"Résultat": "<span class='ok'>conforme</span>" if ok else "<span class='ecart'>à vérifier</span>",
              "Contrôle": e(c), "Constat": e(res_)} for c, res_, ok in ctrl_d.itertuples(index=False)])
    st.markdown("<div class='section'>Sources</div>", unsafe_allow_html=True)
    st.markdown("\n".join(f"- {v}" for v in SOURCES.values()))
    st.markdown(f"<div class='section'>Méthode de calcul</div>{e(METHODE)}<br>Période : {e(moteur.donnees.periode())}.",
                unsafe_allow_html=True)
    st.markdown("<div class='section'>Correction appliquée</div>CNQ.TO, 22 août 2022 : un « fractionnement » de 1,021 et une "
                "distribution de 0,75 $ sont enregistrés le même jour, ce qui compte la distribution deux fois dans la clôture ajustée. "
                "Le facteur 1,021 est retiré avant cette date.", unsafe_allow_html=True)
    st.markdown("<div class='section'>Preuves ESG documentées</div>", unsafe_allow_html=True)
    esg = moteur.outils.esg
    if len(esg):
        tableau(["Actif", "Type", "Constat", "Source", "Date"],
                [{"Actif": e(x.symbole), "Type": e(x.type), "Constat": e(x.constat),
                  "Source": f"<a href='{e(x.url)}' target='_blank'>{e(x.source)}</a>", "Date": e(x.date_publication)}
                 for x in esg.itertuples()])
        st.markdown("<div class='mention'>Une poursuite rapporte des allégations, pas un jugement. Un actif sans preuve "
                    "documentée n'est ni validé ni exclu : l'outil indique que l'information manque.</div>", unsafe_allow_html=True)
    st.markdown("<div class='section'>Univers de 31 actifs</div>", unsafe_allow_html=True)
    u = moteur.donnees.univers.reset_index()
    tableau(["Symbole", "Nom", "Classe", "Devise", "Secteur"],
            [{"Symbole": e(x.ticker), "Nom": e(x.name), "Classe": e(x.asset_class), "Devise": e(x.currency), "Secteur": e(x.sector)}
             for x in u.itertuples()])

# ---------------------------------------------------------------------------
# Onglet Méthode
# ---------------------------------------------------------------------------

with ong_methode:
    st.markdown("#### Comment l'avis est produit")
    st.graphviz_chart("""
    digraph G {
      rankdir=LR; bgcolor="transparent";
      node [shape=box, style="filled", fontname="Helvetica", fontsize=10, color="#d0d5dd", fillcolor="#ffffff", penwidth=1];
      edge [fontname="Helvetica", fontsize=9, color="#667085", fontcolor="#475467"];
      U [label="Demande\\n+ profil"];
      C [label="Claude Sonnet 5\\nAmazon Bedrock\\n(choix des calculs, rédaction)", fillcolor="#eef3f8", color="#1f5f8b"];
      O [label="Calculs Python\\nindicateurs · simulation\\nvérification · ESG"];
      D [label="Données publiques\\nYahoo Finance · Banque du Canada\\npreuves ESG sourcées"];
      G [label="Contrôle de cohérence\\nchiffres · alternative · verdict"];
      A [label="Avis expliqué"];
      T [label="Trace JSON"];
      U -> C; C -> O [label="demande un calcul"]; O -> D; O -> C [label="résultat"];
      C -> G [label="avis proposé"]; G -> C [label="écart : correction", style=dashed, color="#b42318", fontcolor="#b42318"];
      G -> A [label="accepté"]; A -> T [style=dotted];
    }""")
    tableau(["Composant", "Rôle", "Pourquoi"],
            [{"Composant": "<b>Claude sur Amazon Bedrock</b>", "Rôle": "Interprète la demande, choisit les calculs, construit et corrige une alternative, rédige l'avis.",
              "Pourquoi": "Relier la demande, le profil et les résultats, et l'expliquer simplement."},
             {"Composant": "<b>Calculs Python</b>", "Rôle": "Produisent tous les chiffres : risque, simulation avant/après, respect des règles, preuves ESG.",
              "Pourquoi": "Des chiffres exacts et reproductibles. Le modèle ne calcule rien lui-même."},
             {"Composant": "<b>Contrôle de cohérence</b>", "Rôle": "Vérifie que chaque chiffre de l'avis apparaît dans le calcul cité, que l'alternative a été vérifiée et que le verdict ne contredit pas les règles.",
              "Pourquoi": "Empêcher une explication qui ne correspond pas aux calculs."},
             {"Composant": "<b>Trace</b>", "Rôle": "Enregistre chaque étape : calcul, entrée, sortie, requête Bedrock.",
              "Pourquoi": "Permettre de vérifier ce qui a réellement été exécuté."}])
    st.markdown("<div class='section'>Rôle d'AWS</div>Chaque analyse effectue de 4 à 8 appels à Amazon Bedrock (API Converse avec "
                "utilisation d'outils, région us-east-1). Les identifiants de requête figurent dans la trace.", unsafe_allow_html=True)
    st.markdown("<div class='section'>Pourquoi « Cousseil »</div><i>Cousseil</i> mêle <i>coussin</i> et <i>conseil</i>. "
                "En finance personnelle, le « coussin de sécurité » est la réserve qui amortit les coups durs. Cousseil joue ce "
                "rôle pour une décision : il la confronte au profil et aux chocs du passé (dont la baisse simultanée des actions "
                "et des obligations en 2022) avant qu'elle soit prise, pour dormir sur ses deux oreilles. Malgré le clin d'œil, "
                "ce n'est pas un conseil : l'outil vérifie et explique, il ne recommande pas d'achat.", unsafe_allow_html=True)
    st.markdown("<div class='section'>Limites connues</div>", unsafe_allow_html=True)
    st.markdown("""- Indicateurs historiques sur 2021-2026 : ils ne prédisent pas l'avenir, et la volatilité ne résume pas tout le risque.
- Univers de 31 actifs choisi en 2026 : biais du survivant.
- Preuves ESG limitées aux sources documentées à la main ; QQQ est compté entièrement comme technologique.
- Le contrôle vérifie la présence de chaque chiffre dans le calcul cité, pas l'interprétation de la phrase qui l'accompagne.""")


st.markdown(f"<div class='pied-produit'><b style='color:#17375e'>{NOM}</b>"
            "<span>Équipe : Louis Thibaudat, Nathan Marie et Virgile Rosin</span><span>Datathon PolyFinances, Polytechnique Montréal · défi AlphaForge AI · Banque Nationale × AWS</span>"
            "<span style='margin-left:auto'>Simulation pédagogique, profils fictifs, aucun conseil financier personnalisé</span></div>",
            unsafe_allow_html=True)

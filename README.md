<img src="assets/logo.svg" width="72" alt="Logo Cousseil">

# Cousseil

**Le coussin de sécurité d'une décision d'investissement, pour dormir sur ses deux oreilles.**
**Équipe :** Louis Thibaudat, Nathan Marie et Virgile Rosin.

Projet réalisé lors du **Datathon PolyFinances** (Polytechnique Montréal), les **14 et 15 novembre 2026**, défi AlphaForge AI proposé par Banque Nationale et AWS.

**Le nom :** *Cousseil* mêle *coussin* et *conseil*. En finance personnelle, le « coussin de sécurité » est la réserve qui amortit les coups durs. Cousseil joue ce rôle pour une décision : il la confronte au profil de l'investisseur et aux chocs du passé (dont 2022) avant qu'elle soit prise, pour dormir sur ses deux oreilles. Malgré le clin d'œil, ce n'est pas un conseil : l'outil vérifie et explique, il ne recommande pas d'achat.

> Simulation pédagogique : profils et portefeuilles fictifs, aucune transaction, aucun conseil financier personnalisé.

Un investisseur décrit ce qu'il veut faire, par exemple « je veux mettre 25 % de mon épargne sur Tesla ». Cousseil :
1. simule l'effet de la demande sur son portefeuille ;
2. la confronte à son profil ;
3. rend un verdict argumenté ;
4. propose, si besoin, une alternative vérifiée.

Chaque chiffre de l'avis provient d'un calcul identifié, et un contrôle de cohérence renvoie l'avis au modèle s'il cite un chiffre qui ne correspond pas aux calculs.

## Fonctionnement

| Composant | Rôle |
|---|---|
| **Agent : Claude Sonnet 5 sur Amazon Bedrock** (API Converse avec outils, `us-east-1`) | Interprète la demande, choisit les calculs, construit et corrige une alternative, rédige l'avis |
| **Calculs Python** (`second_avis.py`) | Indicateurs, simulation avant/après, respect des règles du profil, preuves ESG. Tous les chiffres viennent d'ici. |
| **Contrôle de cohérence** | Vérifie chaque chiffre, l'alternative et le verdict. Renvoie l'avis au modèle en cas d'écart. |
| **Trace** (`traces/*.json`) | Chaque calcul, chaque appel Bedrock (identifiant de requête) et chaque contrôle |
| **Application** (`app.py`, Streamlit) | Analyse, comparaison des trois profils, sensibilité aux hypothèses, données et sources, méthode |

## Lancer l'application

1. Python 3.10 ou plus récent (sous Windows, Microsoft Store ou python.org avec « Add Python to PATH »).
2. `pip install -r requirements.txt`, puis `python -m streamlit run app.py`. Sous Windows, vous pouvez aussi double-cliquer sur `lancer_app.bat`.
3. Dans « Connexion AWS », collez les identifiants temporaires (Workshop Studio, « Get AWS CLI credentials »). Autre option : les coller dans un fichier `identifiants_aws.txt` à la racine (exclu de Git). Dans SageMaker Unified Studio, laissez vide : le rôle de l'espace est utilisé. Sans accès AWS, choisissez « Analyse enregistrée » pour rejouer les 25 analyses réelles du dossier `traces/`.
4. Choisissez un profil et une demande, puis cliquez sur « Analyser la demande ».

« Analyse enregistrée » réaffiche une trace sans appeler AWS. Le test d'accès à Bedrock se lance avec `python smoke_test_bedrock.py --prix prices_daily.csv`.

## Livrables

| Livrable | Fichier |
|---|---|
| Documentation technique | [`docs/documentation_technique.pdf`](docs/documentation_technique.pdf) ([source](docs/documentation_technique.md)) |
| One-pager | [`docs/one_pager.pdf`](docs/one_pager.pdf) |
| Vidéo de démonstration | [`docs/Cousseil_video_finale.mp4`](docs/Cousseil_video_finale.mp4) (5 min 14) · lien YouTube : *à ajouter* · script : [`docs/script_video.md`](docs/script_video.md) |
| Tests | [`docs/tests_resultats.md`](docs/tests_resultats.md) : 8 scénarios sur Bedrock, **8 verdicts conformes** (produit par `python lancer_tests.py`) · sources ESG vérifiées : [`docs/tests.md`](docs/tests.md) |
| Exemples d'exécution réelle | [`traces/`](traces/) |

## Données

| Fichier | Source | Extraction |
|---|---|---|
| `prices_daily.csv`, `assets_universe.csv` | Yahoo Finance via yfinance (jeu de départ des organisateurs), 31 actifs, 2021-11-12 au 2026-11-12 | 2026-11-13 |
| `fx_usdcad_daily.csv` | Banque du Canada, série FXUSDCAD | 2026-11-13 |
| `esg_preuves.csv` | Preuves documentées à la main, avec URL et date (mass.gov, Alberta Energy Regulator, Wisconsin Public Radio, Financial Advisor) | 2026-11-14 |

**Méthode :** analyse en CAD (taux du jour ou dernier taux connu, jamais un taux futur), prix de fin de semaine pour aligner TSX, bourses américaines et cryptoactifs, rendements hebdomadaires annualisés sur 52 semaines, portefeuilles rééquilibrés chaque semaine, sans frais.
**Correction :** CNQ.TO, 2022-08-22. La distribution était comptée deux fois (faux fractionnement de 1,021) ; le facteur est retiré.
**Hypothèses :** les portefeuilles de départ et les seuils des règles sont fixés par l'équipe (`PERSONAS` dans `second_avis.py`). Leur influence est mesurée dans l'onglet « Sensibilité ».

## Limites

Indicateurs historiques non prédictifs · univers choisi en 2026 (biais du survivant) · preuves ESG partielles · QQQ compté entièrement comme technologique · le contrôle vérifie les chiffres cités, pas l'interprétation des phrases.

## Structure

```
app.py                     application Streamlit
second_avis.py             données, calculs, règles des profils, agent, contrôle, graphique
esg_preuves.csv            preuves ESG sourcées
*.csv                      données de marché
smoke_test_bedrock.py      test d'accès à Amazon Bedrock
demo_second_avis_v2.ipynb  démonstration en notebook (secours)
docs/                      documentation technique, one-pager, script vidéo, tests
traces/                    traces d'exécution réelles
lancer_app.bat             lancement sous Windows
lancer_tests.py            scénarios de validation (vrai modèle)
publier_github.bat         publication sur GitHub
```

Conditions d'utilisation des données : Yahoo (https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html), Banque du Canada (https://www.bankofcanada.ca/terms/).

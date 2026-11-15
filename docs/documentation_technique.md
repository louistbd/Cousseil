# Cousseil : documentation technique

**Datathon PolyFinances (Polytechnique Montréal), 14-15 novembre 2026, défi AlphaForge AI (Banque Nationale × AWS).** Simulation pédagogique : profils et portefeuilles fictifs, aucune transaction, aucun conseil financier personnalisé.

**Équipe :** Louis Thibaudat, Nathan Marie et Virgile Rosin.

---

## 1. Problème traité

Un investisseur veut faire un geste précis, souvent sous l'influence de l'actualité : « Tesla est partout dans les nouvelles, je veux y mettre 25 % de mon épargne. » Les outils de courtage exécutent ce genre de demande sans la confronter au profil de la personne.

**Cousseil** sert de coussin de sécurité à une décision : il la confronte au profil et aux chocs du passé avant qu'elle soit prise. Le nom mêle *coussin* (le « coussin de sécurité » de la finance personnelle) et *conseil*, sans en être un : l'outil vérifie et explique, il ne recommande pas d'achat. À partir d'une demande en langage naturel et d'un profil, l'outil :
1. simule l'effet de la demande sur le portefeuille ;
2. la confronte aux contraintes du profil ;
3. rend un verdict : cohérent, cohérent avec réserves, incohérent ou impossible à évaluer ;
4. l'explique avec des chiffres sourcés ;
5. propose, si nécessaire, une alternative vérifiée qui garde l'intention de la personne.

Les trois personas de l'énoncé servent de tests :

| Persona | Test central de l'énoncé | Comportement attendu de Cousseil |
|---|---|---|
| Amira (risque élevé, 15 ans et plus) | « Risque élevé » ne signifie pas « tout est acceptable » | Refuser une concentration extrême et proposer une exposition IA et crypto diversifiée |
| Mateo (modéré, ESG) | Intégrer des préférences non financières avec des preuves | Refuser un titre visé par une controverse documentée, même si ses chiffres sont bons |
| Robert (faible à modéré, 3 à 5 ans) | Détecter une contradiction et ne pas acquiescer | Refuser 25 % sur un titre très volatil et proposer une position limitée |

## 2. Architecture

```
Demande + profil
   │
   ▼
Claude Sonnet 5 (Amazon Bedrock, API Converse avec outils, us-east-1)
   │  choisit et enchaîne les calculs, construit puis corrige une alternative, rédige l'avis
   ▼
Calculs Python déterministes ──► données publiques (prix, change, preuves ESG)
   │
   ▼
Avis structuré (rediger_avis) ──► Contrôle de cohérence (Python)
                                     │  écart : renvoi au modèle (2 fois au maximum)
                                     ▼
                                Avis affiché + trace JSON
```

| Composant | Rôle | Justification |
|---|---|---|
| **Agent (Claude Sonnet 5 sur Bedrock)** | Interprète la demande, décide des calculs à lancer et dans quel ordre, construit une alternative, la fait vérifier, rédige l'avis | Relier une demande libre, un profil et des résultats chiffrés exige du jugement. C'est la valeur ajoutée de l'IA. |
| **Outils de calcul** (`profil_investisseur`, `lister_actifs`, `indicateurs_actif`, `simuler_modification`, `evaluer_portefeuille`, `poids_maximal_compatible`, `preuves_esg`) | Produisent **tous** les chiffres | Des chiffres exacts et reproductibles. Le modèle ne calcule rien. |
| **Rédaction structurée** (`rediger_avis`) | Impose un format : verdict, résumé, 3 à 5 faits reliés à un appel d'outil, tensions, alternative, hypothèses, limites | Rend l'explication vérifiable. C'est le mécanisme d'explicabilité. |
| **Contrôle de cohérence** (gouvernance) | Vérifie que chaque chiffre cité apparaît dans le calcul indiqué, que l'alternative a été vérifiée et respecte les règles, que le verdict ne contredit pas une simulation (« cohérent » malgré un écart, ou « incohérent » sans écart ni preuve ESG) et que l'avis reste concis | Empêche une explication non fidèle à l'exécution. En cas d'écart, l'avis est renvoyé au modèle avec la liste des problèmes. |
| **Trace** | Enregistre chaque appel au modèle (identifiant de requête Bedrock, durée), chaque calcul (entrée, sortie) et chaque contrôle | Audit et reproductibilité |
| **Interface** (Streamlit) | Saisie, déroulé en direct, résultats, comparaison des profils, sensibilité, sources | Rendre les résultats compréhensibles par un non-spécialiste |

**Rôle d'AWS.** Amazon Bedrock héberge le modèle qui pilote l'agent. Sans lui, il n'y a ni choix d'outils, ni alternative, ni avis. Une analyse effectue de 4 à 8 appels Converse. Les identifiants de requête sont conservés dans la trace (voir section 5). Aucune clé n'est versionnée : l'application utilise le rôle de l'environnement ou les identifiants temporaires de l'événement (collés dans l'interface ou dans un fichier local exclu de Git).

**Indicateurs de risque.** Pour chaque actif ou portefeuille : rendement annualisé, volatilité, pire baisse et sa période, **temps de retour au sommet** (en semaines, à comparer à l'horizon du profil), résultat 2022, **perte moyenne des 5 % pires semaines** (risque de queue) et **part du risque** portée par chaque position (contribution à la variance, wᵢ·(Σw)ᵢ / wᵀΣw). Exemple : pour Robert, Tesla à 25 % du capital porte 82 % du risque du portefeuille. L'outil `poids_maximal_compatible` cherche, par pas de 0,5 point, le plus grand poids d'un actif que le profil accepte et la règle qui bloque au-delà (Tesla pour Robert : 5 %, bloqué par la règle « titre très volatil »). L'alternative part de ce chiffre au lieu d'être tâtonnée.

**Performance.** Les consignes et les définitions d'outils sont mises en cache côté Bedrock (`cachePoint`), avec repli automatique si le modèle ne le permet pas. Les sorties d'outils ont été allégées (méthode et sources données une fois dans le profil) : −44 % de texte pour une simulation, −54 % pour une évaluation, ce qui réduit les jetons relus à chaque tour. Le client Bedrock reprend automatiquement en cas de limitation de débit (mode adaptatif, 8 essais). Le modèle est invité à lancer en parallèle les calculs indépendants.

Un seul agent suffit. Les fonctions d'explicabilité et de gouvernance suggérées par l'énoncé sont assurées par la rédaction structurée et par le contrôle de cohérence. Ce dernier est déterministe à dessein : un contrôle doit être plus fiable que ce qu'il contrôle.

## 3. Technologies

| Élément | Choix | Raison |
|---|---|---|
| Modèle | `global.anthropic.claude-sonnet-5` via Bedrock Converse | Testé dans le compte du Datathon ; utilisation d'outils fiable ; Haiku 4.5 reste possible comme modèle plus rapide |
| Calculs | Python, pandas, NumPy | Calculs standards, lisibles et reproductibles |
| Graphiques | matplotlib | Image statique intégrée à la trace, donc rejouable sans recalcul |
| Interface | Streamlit | Application web en Python, rapide à construire et à démontrer |
| Infrastructure | Compte AWS de l'événement (us-east-1) ; exécution locale ou dans SageMaker Unified Studio | Région recommandée par les organisateurs |

### Configuration AWS

| Élément | Configuration |
|---|---|
| Service | Amazon Bedrock Runtime, API **Converse** avec utilisation d'outils (`toolConfig`) : 8 outils, dont l'outil final `rediger_avis` qui impose un avis structuré |
| Modèle et région | `global.anthropic.claude-sonnet-5` (profil d'inférence global), région `us-east-1`, `maxTokens` 4 000 |
| Accès | Identifiants temporaires du compte de l'événement (Workshop Studio) ou rôle de l'espace SageMaker ; permission nécessaire : `bedrock:InvokeModel`. Aucune clé dans le code : saisie dans l'interface, fichier local exclu de Git, ou secrets de l'hébergeur pour la version en ligne |
| Performance | Mise en cache du prompt (`cachePoint` sur les consignes et les outils, repli automatique si non pris en charge) ; client `botocore` en mode de reprise adaptatif (8 essais) contre la limitation de débit ; délai de lecture 120 s |
| Traçabilité | Chaque appel enregistre l'identifiant de requête Bedrock, la durée et les jetons (entrée, sortie, lus en cache) dans `traces/*.json` |
| Coût | Une analyse consomme environ 40 000 à 60 000 jetons en entrée et 3 000 à 6 000 en sortie, pour 20 à 80 s |

**Version en ligne.** L'application est publiée sur Streamlit Community Cloud à partir du dépôt GitHub : https://cousseil-kauuz8xurvmpb9rjpyhnqp.streamlit.app/ Sans identifiants AWS, elle s'ouvre sur les analyses réelles enregistrées pendant le Datathon et permet d'en rejouer le déroulé : les réponses du modèle viennent de la trace, les outils Python sont ré-exécutés en direct (les 25 analyses rejouées redonnent le même verdict). Avec des identifiants placés dans les secrets de l'hébergeur, « Nouvelle analyse » appelle Bedrock en direct.

## 4. Données

### Sources
| Fichier | Contenu | Source | Date d'extraction |
|---|---|---|---|
| `prices_daily.csv` | Prix quotidiens de 31 actifs, colonne `adj_close` (ajustée dividendes et fractionnements) | Yahoo Finance via yfinance (jeu de départ des organisateurs) | 2026-11-13 |
| `fx_usdcad_daily.csv` | Taux USD/CAD | Banque du Canada, série FXUSDCAD | 2026-11-13 |
| `assets_universe.csv` | Univers, classes, devises, secteurs | Organisateurs | 2026-11-13 |
| `esg_preuves.csv` | Preuves ESG documentées à la main, avec URL et date | Voir ci-dessous | 2026-11-14 |

Preuves ESG retenues :

| Actif | Type | Constat | Source |
|---|---|---|---|
| XOM | Controverse | Poursuite du procureur général du Massachusetts (2019) : allégations de tromperie des investisseurs et des consommateurs sur les risques climatiques. Allégations, pas un jugement. | mass.gov |
| ENB.TO | Controverse | Line 5 : occupation illégale de terres de la bande Bad River, constatée en 2023 et confirmée en appel le 2026-07-30 | Wisconsin Public Radio |
| CNQ.TO | Controverse | Amende de 278 000 $ de l'Alberta Energy Regulator après plus de 400 oiseaux morts sur un bassin de résidus (décision 2025 ABAER 007) | AER |
| ESGV | Méthodologie | L'indice FTSE US All Cap Choice exclut notamment les combustibles fossiles, les armes, le tabac et le nucléaire | Financial Advisor |

Sans preuve documentée, l'outil **ne conclut pas** : ni validé, ni exclu. Le secteur énergie à lui seul n'est pas traité comme une preuve.

### Traitements
- **Devise :** analyse en CAD. Les prix en USD sont multipliés par le taux de la Banque du Canada du jour, ou par le dernier taux connu (jamais un taux futur).
- **Calendriers :** TSX, bourses américaines et cryptoactifs (7 jours sur 7) n'ont pas les mêmes jours de cotation. On prend le dernier prix connu de chaque semaine (vendredi), puis on calcule des rendements hebdomadaires annualisés sur 52 semaines.
- **Portefeuille :** rééquilibré chaque semaine aux poids indiqués, sans frais ni impôts.
- **Période :** 261 semaines, du 2021-11-19 au 2026-11-13. Elle inclut 2022, année où actions et obligations ont baissé ensemble.
- **Indicateurs :** rendement annualisé, volatilité annualisée, pire baisse du sommet au creux (avec dates), résultat 2022, pire semaine.

### Contrôles de qualité et correction
| Contrôle | Résultat |
|---|---|
| Lignes, doublons, prix positifs | 40 049 lignes, 31 actifs, 0 doublon, tous les prix positifs |
| **CNQ.TO, 2022-08-22** | Clôture ajustée +2,8 % contre +0,6 % en recalculant clôture + distribution de 0,75 $. Un faux « fractionnement » de 1,021 compte la distribution deux fois. **Correction :** facteur retiré avant cette date. Effet : rendement annualisé de 28,5 % à 28,0 %. Désactivable (`corriger_donnees=False`). |
| Volumes nuls | ZST.TO, 2022-07-06 : prix conservé, signalé |
| Change | 60 jours ouvrables sans taux (fériés canadiens) : dernier taux reporté |

### Hypothèses de l'équipe (réglables dans `PERSONAS`)
Les portefeuilles de départ et les seuils sont fictifs et choisis par l'équipe. Ils ne viennent pas de l'énoncé.

| Persona | Règles |
|---|---|
| Amira | Titre individuel ≤ 15 % · crypto ≤ 10 % · technologie ≤ 50 % · au moins 6 positions · pire baisse ≥ −45 % |
| Mateo | Titre ≤ 10 % · crypto 0 % · obligations ≥ 30 % · volatilité ≤ 12 % · pire baisse ≥ −20 % · aucune controverse ESG documentée |
| Robert | Titre ≤ 10 % · crypto 0 % · titre très volatil (> 40 %) ≤ 5 % · obligations ≥ 40 % · volatilité ≤ 10 % · pire baisse ≥ −15 % |

## 5. Explicabilité : exemple réel de trace

**Demande d'Amira :** « Je veux tout mettre dans l'IA et la crypto : NVIDIA, Bitcoin et Ether. » Analyse du 14 novembre 2026, 15 h 46, 55 s, `traces/avis_amira_20261114_154657.json`.

| Étape | Exécution réelle |
|---|---|
| Appel modèle (requête `7bcbd50c…`) | Claude demande A1 `profil_investisseur(amira)` et A2 `lister_actifs` |
| Appel modèle (`0003512f…`) | A3 à A5 `indicateurs_actif` sur NVDA, BTC-USD et ETH-USD ; A6 `evaluer_portefeuille` sur NVDA 34 %, BTC 33 %, ETH 33 % |
| Appel modèle (`cc278bb5…`) | A7 `evaluer_portefeuille` sur une alternative diversifiée |
| Appel modèle (`62ab1641…`) | Premier avis proposé |
| **Contrôle** | **2 écarts détectés.** L'avis attribuait la pire baisse d'Ether (−74,9 %) au calcul A4, qui porte sur Bitcoin, et citait « 5 règles » absent du calcul A6. L'avis est renvoyé au modèle. |
| Appel modèle (`daca23c6…`) | Avis corrigé, 8 contrôles sur 8 réussis, accepté |

**Avis final :** incohérent. Le portefeuille demandé respecte 1 règle sur 5 : pire baisse historique −65,0 % contre −45 % toléré, crypto 66,0 % contre 10 % maximum. L'alternative vérifiée (NVDA 12 %, BTC 6 %, ETH 4 %, QQQ 20 %, SPY 20 %, XIU.TO 15 %, CNR.TO 8 %, XBB.TO 10 %, GLD 5 %) respecte les 5 règles, avec une pire baisse de −28,6 %. Chaque chiffre de l'avis est relié à l'identifiant du calcul qui l'a produit.

Cet exemple montre que l'explication est **liée à l'exécution réelle** : une citation mal attribuée a été détectée et corrigée avant affichage.

## 6. Validation

**8 scénarios rejoués sur le vrai modèle** (Amazon Bedrock, 14 novembre 2026, 17 h 18, `lancer_tests.py`) : **8 verdicts conformes à l'attendu sur 8**, 8 contrôles de cohérence sur 8 réussis pour chaque avis final. Détail et résumé de chaque avis : `docs/tests_resultats.md`.

| # | Profil | Demande | Attendu | Obtenu | Renvois | Durée |
|---|---|---|---|---|---|---|
| 1 | Robert | 25 % de Tesla | incohérent | incohérent | 0 | 23 s |
| 2 | Amira | 25 % de Tesla | incohérent ou réserves | incohérent | 1 | 38 s |
| 3 | Amira | Tout en NVIDIA, Bitcoin, Ether | incohérent | incohérent | 0 | 41 s |
| 4 | Mateo | 8 % d'Exxon Mobil | incohérent ou réserves | incohérent | 0 | 41 s |
| 5 | Robert | 5 % de Palantir (hors données) | impossible à évaluer | impossible à évaluer | 1 | 46 s |
| 6 | Mateo | 10 % d'Enbridge | incohérent | incohérent | 2 | 77 s |
| 7 | Robert | 20 % de Bitcoin | incohérent | incohérent | 0 | 35 s |
| 8 | Amira | +10 % de QQQ | cohérent ou réserves | cohérent avec réserves | 2 | 51 s |

Points clés : pour Robert et Tesla, la volatilité passe de 6,5 % à 16,2 %, la pire baisse de −9,8 % à −23,6 %, et Tesla porterait 82 % du risque du portefeuille pour 25 % du capital ; l'alternative limitée à 5 % est vérifiée. Pour Mateo et Exxon, les chiffres s'améliorent (pire baisse −10,9 %) : seule la règle ESG, appuyée par une preuve datée, justifie le refus. Pour Palantir, absent des données, aucun chiffre n'est inventé. Les renvois montrent le contrôle de cohérence à l'œuvre : 4 avis sur 8 sont passés du premier coup ; les 4 autres ont été renvoyés 1 ou 2 fois, puis corrigés avant affichage.

*Vérification des sources ESG : `docs/tests.md`.*

**Sensibilité aux hypothèses** (onglet « Sensibilité ») : les seuils sont multipliés par 0,75 (plus stricts), 1,25 et 1,5 (plus souples).
- Robert, 25 % de Tesla : non conforme à **tous** les réglages (au mieux 2 règles sur 6). Le verdict ne dépend pas d'un réglage fin.
- Robert, alternative à 5 % de Tesla : conforme au réglage de référence et en plus souple, mais 3 règles sur 6 seulement avec des seuils plus stricts. Une conclusion fragile, à présenter comme telle.
- Amira, NVIDIA + Bitcoin + Ether : non conforme à tous les réglages.

**Contrôles automatiques :** qualité des données (section 4) et cohérence de chaque avis (section 2), affichés dans l'interface et la trace.

## 7. Limites

- Indicateurs historiques sur 5 ans : ils ne prédisent pas l'avenir. La volatilité et la pire baisse ne couvrent ni la liquidité ni le risque réglementaire.
- Univers de 31 actifs choisi en 2026 : biais du survivant.
- Preuves ESG limitées à quatre actifs documentés à la main. QQQ est compté entièrement comme technologique, faute de composition détaillée.
- Seuils et portefeuilles de départ fictifs. La sensibilité montre leur influence sans les justifier statistiquement.
- Le contrôle de cohérence vérifie la présence de chaque chiffre dans le calcul cité, pas l'interprétation de la phrase qui l'accompagne.
- Les données macroéconomiques fournies ne sont pas utilisées.

## 8. Améliorations envisagées

- Preuves ESG plus larges : SEDAR+, SEC EDGAR, rapports de durabilité, composition des FNB.
- Contexte macro (taux 2022) pour expliquer la baisse simultanée des actions et des obligations, avec dates de publication.
- Profil réel du client, avec son consentement, et seuils calibrés par un conseiller.
- Archivage des traces sur Amazon S3 et garde-fous Amazon Bedrock Guardrails.
- Contrôle sémantique des phrases (en plus des chiffres).

## 9. Reproduire

```
pip install -r requirements.txt
python -m streamlit run app.py      # ou double-clic sur lancer_app.bat sous Windows
```
Dans l'application, collez les identifiants temporaires AWS (Workshop Studio, « Get AWS CLI credentials », région us-east-1), ou placez-les dans `identifiants_aws.txt` (exclu de Git). Les 8 scénarios se relancent avec `python lancer_tests.py`. Dans SageMaker Unified Studio, laissez vide : le rôle de l'espace est utilisé. Le mode « Analyse enregistrée » réaffiche les traces sans appeler AWS. Le test rapide d'accès à Bedrock se lance avec `python smoke_test_bedrock.py --prix prices_daily.csv`.

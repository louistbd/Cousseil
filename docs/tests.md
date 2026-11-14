# Tableau de tests

Les résultats automatiques de ces scénarios sont produits par `python lancer_tests.py`, dans `docs/tests_resultats.md`.

Chaque test se lance dans l'application (onglet Analyse). La trace est enregistrée automatiquement dans `traces/`.

| # | Profil | Demande | Verdict attendu | Verdict obtenu | Chiffres cohérents avec le tableau ? | Explication claire ? | Trace | Commentaire |
|---|---|---|---|---|---|---|---|---|
| 1 | Robert | 25 % de Tesla | Incohérent | Incohérent | Oui | | | Vérifié le 14/11 |
| 2 | Amira | 25 % de Tesla | Réserves ou incohérent, avec plus de marge que pour Robert | | | | | |
| 3 | Amira | Tout en NVIDIA, Bitcoin et Ether | Incohérent | Incohérent | Oui | Oui | avis_amira_20261114_154657.json | Contrôle : 2 écarts corrigés |
| 4 | Mateo | 8 % d'Exxon Mobil | Non conforme ESG (preuve sourcée) | | | | | |
| 5 | Robert | 5 % de Palantir | Impossible à évaluer | Impossible à évaluer | Aucun chiffre inventé | | | Vérifié le 14/11 |
| 6 | Mateo | 10 % d'Enbridge | Non conforme ESG | | | | | |
| 7 | Robert | 20 % de Bitcoin | Incohérent (crypto à 0 %) | | | | | |
| 8 | Amira | +10 % de QQQ | Cohérent ou réserves (techno ≤ 50 %) | | | | | |

## Vérification des sources ESG

| Actif | URL ouverte ? | La page dit-elle ce que nous affirmons ? | Vérifié par |
|---|---|---|---|
| XOM | Oui | Oui : plainte du 24 octobre 2019, plainte amendée le 5 juin 2020, allégations de tromperie sur les risques climatiques | Claude, 14/11 |
| ENB.TO | Oui | Oui : la Cour d'appel du 7e circuit confirme l'occupation illégale (décision rapportée le 5 août 2026, rendue un jeudi, probablement le 30 juillet). La fermeture n'est pas immédiate, des dommages sont à recalculer. | Claude, 14/11 |
| CNQ.TO | Oui | Oui : pénalité de 278 000 $ confirmée par l'AER le 7 août 2025, plus de 400 oiseaux morts en juillet-août 2022. Le chiffre de 411 (presse) ne figure pas dans la décision : nous écrivons « plus de 400 ». | Claude, 14/11 |
| ESGV | Oui | Oui : l'indice FTSE US All Cap Choice exclut fossiles, armes, tabac et nucléaire. L'article n'affiche pas de date précise (lancement en septembre 2018). | Claude, 14/11 |

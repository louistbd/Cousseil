# Résultats des tests de validation

Exécutés le 2026-11-14 à 17:18 avec le modèle global.anthropic.claude-sonnet-5 sur Amazon Bedrock (us-east-1). Script : `lancer_tests.py`. **8 verdict(s) conforme(s) à l'attendu sur 8.**

| # | Profil | Demande | Attendu | Obtenu | Conforme | Contrôles | Renvois au modèle | Calculs | Durée (s) | Trace |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Robert | Tesla est partout dans les nouvelles, je veux y mettre 25 % de mon épargne. | incohérent | incohérent | oui | 8/8 | 0 | 4 | 23.0 | `avis_robert_20261114_171213_531.json` |
| 2 | Amira | Tesla est partout dans les nouvelles, je veux y mettre 25 % de mon épargne. | incohérent ou réserves | incohérent | oui | 8/8 | 1 | 5 | 38.0 | `avis_amira_20261114_171236_772.json` |
| 3 | Amira | Je suis jeune, je veux tout mettre dans l'IA et la crypto : NVIDIA, Bitcoin et Ether. | incohérent | incohérent | oui | 8/8 | 0 | 6 | 41.2 | `avis_amira_20261114_171314_872.json` |
| 4 | Mateo | Exxon a très bien performé, je pense ajouter 8 % d'Exxon Mobil à mon portefeuille. | incohérent ou réserves | incohérent | oui | 8/8 | 0 | 8 | 40.8 | `avis_mateo_20261114_171356_126.json` |
| 5 | Robert | Je veux acheter 5 % de Palantir, tout le monde en parle. | impossible à évaluer | impossible à évaluer | oui | 8/8 | 1 | 4 | 45.7 | `avis_robert_20261114_171437_018.json` |
| 6 | Mateo | Je veux ajouter 10 % d'Enbridge pour les dividendes. | incohérent | incohérent | oui | 8/8 | 2 | 8 | 76.5 | `avis_mateo_20261114_171522_793.json` |
| 7 | Robert | Je pense mettre 20 % de mon portefeuille en Bitcoin. | incohérent | incohérent | oui | 8/8 | 0 | 5 | 35.0 | `avis_robert_20261114_171639_427.json` |
| 8 | Amira | J'aimerais ajouter 10 % de QQQ pour plus de croissance. | cohérent ou réserves | cohérent avec réserves | oui | 8/8 | 2 | 5 | 51.1 | `avis_amira_20261114_171714_583.json` |

## Objet de chaque test et résumé de l'avis

**1. Robert** : Doit refuser : titre très volatil, horizon court.  
> Mettre 25 % de votre épargne dans Tesla ne correspond pas à votre profil « risque faible à modéré » axé sur la préservation du capital avant la retraite : cela ferait exploser le risque du portefeuille (volatilité, pire perte) et violerait plusieurs règles de prudence de l'équipe. Une exposition beaucoup plus modeste (5 %) permettrait de suivre votre intérêt pour Tesla sans déséquilibrer votre portefeuille. Les performances passées de Tesla, très volatiles, ne garantissent rien pour l'avenir.

**2. Amira** : Doit être moins sévère que pour Robert, mais 25 % dépasse le poids maximal d'un titre.  
> Mettre 25 % de ton épargne dans Tesla dépasse la limite de concentration par titre (15 % max) fixée pour ton profil, même si tu acceptes un risque élevé. Cette concentration ferait aussi grimper la perte maximale historique du portefeuille et sa volatilité de façon notable. Une alternative à 15 % dans Tesla reste conforme à toutes tes règles tout en gardant une forte exposition à ce titre.

**3. Amira** : Risque élevé ne veut pas dire tout permis.  
> Mettre tout votre portefeuille dans NVIDIA, Bitcoin et Ether est trop concentré pour votre profil, même s'il est offensif : vous perdriez la diversification que vous souhaitez vous-même garder. Avec ce scénario (NVDA 34 %, BTC 33 %, ETH 33 %), la perte historique maximale atteindrait -65 %, bien au-delà de la limite de -45 % retenue pour vous, et 4 des 5 règles de votre profil seraient violées. Une alternative qui garde votre inclinaison pour l'IA et la crypto, mais dans des proportions limitées, reste conforme à votre profil tout en offrant un bon potentiel de croissance.

**4. Mateo** : La preuve ESG (poursuite climatique) doit peser malgré de bons chiffres.  
> Ajouter 8 % d'Exxon Mobil ferait respecter les limites de risque de Mateo, mais pas sa règle ESG : une controverse documentée (poursuite du Massachusetts pour tromperie sur les risques climatiques) est associée à Exxon. Comme l'ESG est une priorité explicite de Mateo, cette position n'est pas cohérente avec son profil, même si les chiffres de rendement passé sont attractifs. Une alternative sans controverse documentée, qui renforce les actions via un FNB déjà sélectionné pour ses critères ESG, permet de garder l'intention de croissance tout en respectant toutes les règles.

**5. Robert** : Actif hors des données : aucun chiffre inventé.  
> Palantir (PLTR) ne fait pas partie des données disponibles, donc impossible de chiffrer son risque ou d'évaluer l'impact réel de cet achat sur le portefeuille de Robert. Même sans ces chiffres, l'intention - mettre 5 % dans un seul titre technologique très médiatisé - va à l'encontre du profil « risque faible à modéré » de Robert, qui privilégie la stabilité et vise à préserver son capital avant la retraite. Une alternative diversifiée (via un FNB technologique) permettrait de garder un peu d'exposition à la tendance sans concentrer le risque sur un seul titre.

**6. Mateo** : Controverse documentée (Line 5) et poids maximal dépassé.  
> Ajouter 10 % d'Enbridge (ENB.TO) va à l'encontre d'une préférence clé de Mateo : éviter les entreprises avec des controverses environnementales ou sociales documentées. Une controverse est effectivement documentée (occupation illégale de terres autochtones, confirmée en appel en 2026), donc même si les mesures de risque restent dans les limites, cette position viole la règle ESG de son profil. Une alternative conforme et proche de son intention (revenu de dividende, secteur stable) consiste à renforcer Fortis (FTS.TO), déjà présente dans son portefeuille, sans controverse documentée.

**7. Robert** : Crypto exclue du profil (0 %).  
> Mettre 20 % du portefeuille en Bitcoin ne colle pas au profil de Robert, qui vise la préservation du capital avec un risque faible à modéré et qui dit explicitement être peu intéressé par les cryptoactifs. La simulation montre que cette décision ferait grimper fortement le risque et casserait six règles prudentielles du profil, dont la perte historique maximale (-22,5 % contre -15 % toléré). Une alternative sans crypto, qui augmente un peu la part actions diversifiées, garde l'intention de croissance tout en respectant toutes les règles de Robert.

**8. Amira** : FNB diversifié, la part technologique reste à vérifier.  
> Amira veut ajouter 10 points de QQQ (passer de 25 % à 35 %), mais cela ferait grimper la part technologie du portefeuille à 52,3 %, au-dessus du seuil de 50 % fixé par son profil, même si la perte historique maximale resterait sous sa limite de -45 %. Une hausse plus modérée, à 30 % de QQQ, permet de renforcer la croissance technologique tout en respectant toutes ses règles. Je propose donc cette version ajustée comme alternative.

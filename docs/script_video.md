# Script de la vidéo de démonstration (environ 5 minutes)

Enregistrement : écran de l'application Cousseil (fenêtre plein écran, zoom du navigateur à 110 %) avec une voix off. Les analyses peuvent être lancées à l'avance puis rejouées en mode « Analyse enregistrée » pour éviter les temps d'attente.

| Temps | À l'écran | Voix off |
|---|---|---|
| 0:00 – 0:25 | Titre « Cousseil » | « Robert a 59 ans et prend sa retraite dans quelques années. Tesla fait la une, et il veut y placer 25 % de son épargne. Son application de courtage exécuterait l'ordre sans rien demander. Cousseil vérifie cette décision avant qu'elle soit prise. » |
| 0:25 – 1:00 | Onglet Méthode, schéma | « Un agent, le modèle Claude hébergé sur Amazon Bedrock, lit la demande et le profil, puis choisit les calculs à lancer. Les chiffres sont produits par du code Python sur des données publiques, jamais par le modèle. Avant d'être affiché, l'avis passe un contrôle de cohérence : chaque chiffre doit provenir du calcul cité, sinon l'avis est renvoyé au modèle. » |
| 1:00 – 2:10 | Analyse, Robert, « Tesla, 25 % » : déroulé en direct puis résultat | « L'agent lit le profil, récupère les indicateurs de Tesla et simule le portefeuille. Verdict : incohérent. La volatilité passerait de 6,5 % à 16,2 %, la pire baisse historique de −9,8 % à −23,6 %. Une seule règle du profil sur six resterait respectée. Cousseil propose une position limitée, vérifiée par un nouveau calcul. » Montrer le tableau « Ce qui fonde l'avis » et la colonne « Calcul source ». |
| 2:10 – 2:50 | Comparer les profils, même demande | « La même demande ne reçoit pas la même réponse selon le profil. Pour Amira, qui accepte davantage de risque, la marge est plus grande, mais une concentration de 25 % sur un seul titre dépasse toujours ses règles. » |
| 2:50 – 3:35 | Analyse, Mateo, « Exxon Mobil, 8 % » | « Pour Mateo, Exxon améliore les chiffres de son portefeuille. Mais Mateo veut éviter les controverses environnementales, et une preuve documentée existe : une poursuite du procureur général du Massachusetts sur les risques climatiques. La préférence non financière l'emporte, et la source est citée. » Montrer l'onglet Données et sources, tableau ESG. |
| 3:35 – 4:15 | Contrôles de cohérence et trace (Amira, analyse enregistrée) | « Ici, le contrôle a détecté que l'avis attribuait la perte d'Ether au calcul de Bitcoin. L'avis a été renvoyé et corrigé avant affichage. Chaque étape est tracée, avec l'identifiant de la requête Amazon Bedrock. Et quand une donnée manque, comme pour Palantir, Cousseil répond qu'il ne peut pas évaluer. » |
| 4:15 – 4:40 | Onglet Sensibilité | « Nos seuils sont des hypothèses. Nous les rendons plus stricts ou plus souples : pour Robert, la conclusion ne change pas. Quand elle change, l'outil le signale. » |
| 4:40 – 5:00 | Retour au titre | « Cousseil : une fonction qu'une banque peut intégrer à sa plateforme de courtage, pour vérifier la cohérence entre une demande et un profil, avec une trace d'audit. Simulation pédagogique, aucun conseil personnalisé. Merci. » |

**À ne pas dire :** « l'IA a calculé » (c'est Python), « Exxon est coupable » (ce sont des allégations), « nos règles sont officielles » (ce sont des hypothèses).
**À masquer :** les identifiants AWS (ne pas ouvrir « Connexion AWS » pendant l'enregistrement).

# TEDT 2.0 — Lot 0
## Documentation technique : provenance, validation, imputation, simulation et sécurité

Version : Lot 0 — 17 novembre 2026

## 1. Principes de fonctionnement

TEDT possède deux modes exclusifs :

- `DEMONSTRATION` : tous les jeux disponibles proviennent du générateur synthétique. Les imports de session ne sont jamais utilisés dans ce mode.
- `REAL_DATA` : seuls les jeux importés et revalidés par `validate_dataset` sont exposés. Les autres jeux sont des DataFrames vides et portent la provenance `unavailable`. Aucune donnée synthétique n'est utilisée comme valeur de remplacement.

Les modes ne se mélangent pas. Un changement de mode efface les résultats de simulation et l'état de conversation afin d'éviter la réutilisation accidentelle d'un résultat calculé dans l'autre mode.

### Statuts de provenance

| Statut | Signification | Interprétation |
|---|---|---|
| `synthetic` | Généré par le générateur de démonstration | Illustratif, jamais une observation réelle |
| `imported_unverified` | Import utilisateur, contrôles structurels réussis | Origine officielle non certifiée par TEDT |
| `unavailable` | Jeu absent ou non importable dans le mode courant | Tout calcul qui en dépend est bloqué |

Le mode `REAL_DATA` signifie « sans substitution synthétique », pas « données officielles certifiées ». L'authenticité et l'autorisation d'utilisation des fichiers restent à confirmer par leur propriétaire institutionnel.

## 2. Dépendances des modules en mode REAL_DATA

| Module | Jeux requis | Comportement si indisponible |
|---|---|---|
| Dashboard national | `institutions`, `results` | Blocage si l'un manque ; indicateurs optionnels affichés comme indisponibles |
| Observatoire | Aucun jeu analytique obligatoire | Accessible pour examiner et préparer les imports |
| Analyse des apprentissages | `results`, `exam_items`, `curriculum` | Blocage sans données réelles d'examens et de programmes |
| Alerte précoce | `students` | Blocage ; aucun dossier élève réel n'est importé dans Lot 0 |
| Équité territoriale | `institutions` | N'affiche que les indicateurs disponibles ; les composantes manquantes ne sont pas imputées |
| Laboratoire de simulation | `institutions` et indicateurs complets équipement/qualité/décrochage/besoin | Blocage si une entrée obligatoire manque |
| Assistant | `institutions`, `results` | Répond aux questions documentaires ; refuse le classement si les variables requises manquent |
| Rapports | `institutions`, `results`, qualité et décrochage complets | Blocage si les indicateurs requis sont incomplets |

Les jeux `exam_items`, `curriculum`, `students` et `context` ne disposent pas de connecteur/import réel dans Lot 0. Ils ne sont donc pas remplacés par leurs versions synthétiques en mode réel.

## 3. Schémas d'import autorisés dans Lot 0

Aucune donnée individuelle d'élève ou d'enseignant n'est acceptée par les imports de cette phase.

### 3.1 `institutions`

Colonnes obligatoires :

- `governorate`
- `level` (`primary` ou `secondary`)
- `pupils`
- `teachers`
- `classes`

Colonnes facultatives :

- `institution_id`
- `equipment_index`
- `mean_score`
- `dropout_rate`
- `lat`
- `lon`

Contrôles : valeurs positives pour les effectifs, bornes des indices et taux, coordonnées géographiques, gouvernorat reconnu, cycle valide, détection des identifiants institutionnels dupliqués. Si l'identifiant officiel est absent, les doublons de lignes strictement identiques sont détectés et TEDT avertit que le rapprochement inter-jeux n'est pas garanti.

### 3.2 `results`

Colonnes obligatoires :

- `governorate`
- `year`
- `level`
- `subject`
- `mean_score`

Colonnes facultatives :

- `pass_rate`
- `candidate_count`

Contrôles : année entière comprise entre 1900 et 2100, cycle valide, matière connue, score entre 0 et 100, taux entre 0 et 1, effectif de candidats entier strictement positif, unicité de la clé gouvernorat/année/cycle/matière.

Le taux de réussite agrégé n'est pas calculé sans `candidate_count`. Les effectifs scolarisés ne sont pas utilisés comme substitut du nombre de candidats. Le dashboard n'agrège pas les cycles primaire et secondaire dans un taux national unique.

## 4. Score de qualité et statuts des valeurs

Le score de qualité n'est pas un score de certification. Il s'agit d'un indicateur de complétude et de rétention des observations.

Formule :

`Score = 100 × (0,70 × couverture_obligatoire + 0,20 × couverture_optionnelle_fournie + 0,10 × taux_de_rétention)`

- Une colonne obligatoire absente entraîne un échec de validation et un score nul.
- Une valeur obligatoire absente ou invalide entraîne le rejet de la ligne.
- Une valeur facultative absente reste manquante et n'est jamais remplacée par zéro.
- Les colonnes facultatives non fournies ne sont pas comptées comme des colonnes obligatoires manquantes.
- Les valeurs hors bornes des champs facultatifs sont transformées en valeurs manquantes, avec avertissement et baisse de complétude.
- Les lignes rejetées sont exportables avec leur motif.

Les compteurs distinguent :

- `missing` : valeur nulle ou vide ;
- `not_applicable` : valeur explicitement déclarée non applicable (`n/a`, `not applicable`, `غير منطبق`, etc.) ;
- `invalid` : valeur non convertible ou hors domaine autorisé ;
- `missing_columns` : colonnes obligatoires absentes ;
- `rejected` : observations écartées des jeux actifs.

Le score ne certifie ni la représentativité, ni l'exactitude de la source, ni l'absence de biais.

## 5. Politique d'imputation

Le module `tedt_core/missing_data.py` centralise la politique.

- Stratégie par défaut : `none`.
- Toute valeur manquante dans une variable déclarée obligatoire bloque le calcul.
- La stratégie `median` n'est disponible que lorsqu'elle est explicitement demandée par un appelant ; elle renvoie un objet `ImputationAudit` indiquant stratégie, nombre et proportion de cellules imputées, et compte par colonne.
- Le simulateur utilise `none` pour la situation initiale et les résultats simulés. Il n'impute donc aucune variable.

Les calculs descriptifs pondérés utilisent les paires valeur/poids disponibles (`weighted_mean`). Les indicateurs distributifs (Gini, Lorenz, écart interquartile) exigent des vecteurs complets et échouent explicitement en présence de valeurs manquantes. Les modules nationaux (dashboard, équité, simulation, rapports) exigent une couverture des 24 gouvernorats ; l’analyse des apprentissages signale explicitement toute couverture partielle.

## 6. Règles d'agrégation

- Effectifs, enseignants et classes : sommes par gouvernorat et cycle.
- Taille de classe : somme des élèves / somme des classes.
- Ratio élèves/enseignant : somme des élèves / somme des enseignants.
- Moyennes d'indicateurs institutionnels : moyenne pondérée par les effectifs d'élèves lorsque ces effectifs sont valides.
- Résultats d'examens : pondération par `candidate_count` uniquement.
- Comparaisons entre années et cycles : conserver explicitement l'année et le cycle ; ne pas agréger implicitement des populations d'examen différentes.

L'indice de besoin territorial peut être dérivé uniquement si les trois composantes documentées (équipement, qualité, décrochage) sont intégralement disponibles. Il est alors marqué `derived_proxy` et ne doit pas être présenté comme un indice officiel de pauvreté ou de défavorisation.

## 7. Transparence du simulateur et reproductibilité

Les équations existantes du simulateur sont conservées. Les paramètres par défaut restent des hypothèses de travail non calibrées ; aucun résultat de simulation n'est présenté comme une évaluation d'impact.

Chaque scénario sauvegardé conserve :

- paramètres du scénario ;
- hypothèses et coefficients ;
- résultats ;
- provenance du jeu source ;
- empreinte SHA-256 de la table agrégée utilisée ;
- graine Monte-Carlo (`7` dans l'interface actuelle) ;
- version du moteur (`tedt-parametric-simulation-v1`) ;
- acteur enregistré et horodatage.

Les intervalles Monte-Carlo restent des plages de propagation des paramètres déclarés, pas des intervalles de confiance.

Les scénarios historiques de l'ancienne base, sans empreinte source ni version, sont conservés et identifiés par `model_version=legacy`.

## 8. Exports

Les exports analytiques CSV ajoutent les colonnes :

- `__tedt_mode`
- `__tedt_provenance`
- `__tedt_warning`

Les exports de rejets portent également le mode, la provenance de l'import et un avertissement `SOURCE_NOT_CERTIFIED`.

Le PDF ajoute le mode et la provenance des jeux utilisés. La génération française a été testée. La génération arabe requiert `arabic-reshaper`, `python-bidi` et une police compatible ; ces dépendances figurent dans `requirements.txt`, mais n'étaient pas installées dans l'environnement d'audit. TEDT affiche donc une indisponibilité explicite plutôt que de produire un PDF arabe non vérifié.

Les graphiques Plotly comportent un filigrane indiquant le mode de données.

## 9. Sécurité et rôles

`tedt_core/security.py` définit la matrice de permissions :

| Rôle | Permissions |
|---|---|
| viewer | lecture |
| analyst | lecture, import agrégé, sauvegarde de scénario |
| admin | permissions analyst + gestion historique et utilisateurs |

Le module ne réalise pas lui-même l'authentification. Un fournisseur institutionnel OIDC/SSO doit injecter un contexte `tedt_auth` contenant `user_id`, `role` et `provider`. Aucun sélecteur de rôle côté utilisateur n'est exposé.

En attendant ce raccordement :

- les imports en mode `REAL_DATA` sont bloqués sans session authentifiée analyst/admin ;
- la sauvegarde de scénarios sur données importées est bloquée sans rôle analyst/admin ;
- la suppression de l'historique n'est pas exposée dans l'interface ;
- la base SQLite applique les permissions de fichier `0600` lorsque le système le permet ;
- les événements de changement de mode, d'import et de sauvegarde sont journalisés.

**Limite impérative :** cette préparation ne constitue pas une authentification institutionnelle, un RBAC de production ni une certification de sécurité. Ne pas connecter de données individuelles ou confidentielles avant l'intégration SSO, l'audit de sécurité, le chiffrement, la gestion des secrets et la politique de sauvegarde institutionnelle.

## 10. Tests et limites d'exécution

- Baseline avant modification : 49 tests réussis.
- Après Lot 0 : 72 tests réussis, dont les 49 initiaux.
- Compilation Python de l'application, des vues, du noyau et des tests : réussie.
- Tests ajoutés : séparation des modes, revalidation, complétude, rejets, statuts des valeurs, doublons, cycle/année, politique d'imputation, blocage du simulateur, indicateurs, exports, historique, rôles et PDF.

L'environnement d'audit ne contient pas Streamlit ; le démarrage de l'interface et les tests end-to-end interactifs des huit modules n'ont donc pas pu être exécutés. ReportLab permet l'export PDF français ; les bibliothèques de façonnage arabe sont absentes. Ces limites sont signalées dans le bilan Lot 0.

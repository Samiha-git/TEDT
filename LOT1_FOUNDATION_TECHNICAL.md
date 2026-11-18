# TEDT — Mission 03 / Lot 1
## Socle de données éducatives — documentation technique et fonctionnelle

**Version :** Lot 1 — première tranche d'implémentation  
**Statut :** architecture approuvée ; pipeline de staging et registre initial implémentés ; intégration réelle du fichier INS non achevée.

## 1. Périmètre livré dans cette tranche

- Base SQLite dédiée `data/tedt_foundation.sqlite`, distincte de `data/tedt_scenarios.sqlite`.
- Schéma SQL versionné dans `data/foundation/schema.sql`.
- Registre initial de 19 sources dans `data/foundation/source_register.csv`.
- Dictionnaire initial de 7 indicateurs dans `data/foundation/indicator_dictionary.csv`.
- Pipeline générique CSV/XLSX : lecture, profilage, conservation du fichier original, manifeste JSON, SHA-256, métadonnées de lot et contrôle structurel.
- Contrôle d'intégrité SHA-256 à chaque relecture du fichier brut.
- Refus des classifications `CONFIDENTIAL` et `PERSONAL_SENSITIVE` et détection de colonnes manifestement individuelles.
- Tableau de bord de lots et de qualité intégré à l'Observatoire, avec accès FR/AR.
- Démonstration territoriale synthétique du futur indicateur 6–14 ans intégrée au module Équité, uniquement en mode DEMONSTRATION et avec provenance `synthetic_demo_only`.
- Référentiel maître des établissements : UUID interne, identifiant officiel nullable, statut d'identifiant, versions historisées, alias et relations.
- Modèle de Data Warehouse avec dimensions et tables de faits séparées par famille.

## 2. Tables du socle

### Gouvernance et ingestion

- `source` : producteur, URL, statut d'accès et conditions déclarées.
- `dataset` : famille, granularité attendue, classification et version de schéma.
- `ingestion_batch` : période, couverture, granularité, acteur, fichier, SHA-256, format, état et profil.
- `validation_run` : version des règles, résultat et métriques de qualité.
- `validation_issue` : anomalies localisées par variable et ligne.
- `transformation_run` : mapping/version, spécification, acteur, date et empreinte de sortie.

### Référentiel maître des établissements

- `institution` : `tedt_institution_id` UUID interne ; `official_id` nullable ; émetteur ; `id_status`.
- `institution_version` : attributs descriptifs et territoriaux avec dates de validité métier et d'enregistrement.
- `institution_alias` : anciens noms et variantes linguistiques.
- `institution_relation` : fusion, scission, remplacement ou rattachement.

Les clés provisoires sont explicitement `provisional_internal`. Une clé officielle ne peut être enregistrée qu'avec un émetteur et une source référencée. L'unicité de la paire émetteur/identifiant est imposée par SQLite. Aucun rapprochement ni fusion automatique n'est implémenté.

### Dimensions et faits

Dimensions : `dim_period`, `dim_geography`, `dim_education_level`, `dim_sex`, `dim_milieu`, plus les registres `source`, `indicator_dictionary` et le référentiel `institution`.

Tables de faits :

- `fact_enrolment` : effectifs inscrits / population éligible par période, géographie ou établissement, niveau et sexe.
- `fact_staff` : effectifs RH et vacances de postes par période, territoire/établissement, niveau et discipline.
- `fact_infrastructure` : actifs, état et disponibilité par type d'infrastructure.
- `fact_learning_outcome` : candidats, réussites, score moyen et taux publié par population d'évaluation.
- `fact_territorial_indicator` : indicateurs publiés ou calculés documentés au niveau territorial.
- `fact_expenditure` : budget et exécution par exercice, programme, nature, niveau et territoire.
- `fact_observation` : stockage générique long-forme pour les indicateurs harmonisés dont le grain est explicitement conservé.

Chaque fait conserve la source, le lot et le statut qualité. Le modèle est créé mais les chargeurs métiers de ces tables ne sont pas encore activés : aucun jeu de données n'est promu dans le warehouse par le simple import.

## 3. Pipeline d'ingestion actuel

`RECEIVED → PROFILED → VALIDATED` puis états futurs `MAPPED → APPROVED → LOADED`.

États alternatifs : `REJECTED`, `QUARANTINED`, `SUPERSEDED`.

L'import générique actuel :

1. exige les métadonnées de source, période, couverture, granularité, autorisation déclarée, classification et version de schéma ;
2. accepte CSV UTF-8/UTF-8 BOM/CP1256/Latin-1 et XLSX ; le vieux format XLS n'est pas activé ;
3. refuse les fichiers vides et les classifications autres que `PUBLIC` ou `INSTITUTIONAL_NON_SENSITIVE` ;
4. détecte les noms de colonnes correspondant à des identifiants ou attributs individuels manifestes ;
5. conserve les octets originaux sans transformation dans `data/staging/<batch_id>/original.ext` ;
6. crée `manifest.json` et stocke SHA-256, taille, nom initial, acteur, source et profil ;
7. lance un contrôle structurel séparé et journalise les erreurs et avertissements.

Le fichier brut est placé en lecture seule au niveau des permissions du système de fichiers. Le SHA-256 est vérifié lors de chaque relecture ; toute altération est détectée. Cela fournit une immutabilité logique et une détection de modification, pas un stockage WORM certifié.

**Important :** `VALIDATED` dans cette tranche signifie contrôle structurel générique réussi. Cela ne signifie ni validation métier complète, ni harmonisation, ni autorisation juridique, ni certification statistique. Le passage à `APPROVED` et `LOADED` n'est pas exposé.

## 4. Mesure de qualité

Les dimensions sont conservées séparément : disponibilité, complétude, exactitude, cohérence, actualité, unicité, traçabilité et interopérabilité.

Le tableau de bord calcule actuellement :

- disponibilité : présence de lots par source/jeu ;
- complétude : cellules renseignées par variable ;
- unicité : doublons de lignes exactes et clés demandées dans le contrôle structurel ;
- traçabilité : présence de métadonnées et empreinte de fichier ;
- anomalies : erreurs et avertissements journalisés.

Exactitude, cohérence métier, actualité et interopérabilité restent `null` tant que des règles et référentiels propres au jeu ne sont pas définis. Aucun score composite n'est calculé. Les périodes manquantes ne sont pas inférées tant que la périodicité attendue n'est pas enregistrée pour chaque jeu.

Les valeurs nulles ne sont jamais converties en zéro. Le profil conserve le nombre de valeurs manquantes par variable.

## 5. Registre des sources

Le registre comporte 19 fiches. Il utilise les six statuts demandés :

1. Disponible et accessible ;
2. Disponible sous conditions d'autorisation ;
3. Partiellement disponible ;
4. À demander à l'institution propriétaire ;
5. Existence à confirmer ;
6. Non disponible ou non vérifié.

La présence d'une page ou d'une publication publique n'est pas interprétée comme un accès à la base administrative détaillée. Les conditions de réutilisation doivent être vérifiées séparément.

La page officielle INS RGPH 2024 identifie un fichier XLSX « Scolarisation (6–14 ans) » et son lien direct est enregistré dans le registre. Le fichier binaire n'a pas pu être récupéré dans l'environnement de développement ; son contenu, ses onglets, son grain, ses dénominateurs et ses métadonnées internes n'ont donc pas été inspectés. Le pilote n'est pas déclaré intégré.

## 6. Dictionnaire des indicateurs

Le dictionnaire initial comporte sept fiches. Les fiches relatives au RGPH 2024 restent provisoires tant que les définitions, formules, numérateurs, dénominateurs, unité et désagrégations ne sont pas confirmés dans le classeur et sa documentation INS.

Un code TEDT est un identifiant interne, pas un code officiel. Une valeur publiée peut être conservée avec son étiquette et sa source, mais elle n'est pas recalculée tant que la définition n'est pas complète. Les valeurs manquantes restent manquantes.

Les indicateurs sont classés dans les catégories de résultats, ressources, processus, réalisations ou impacts lorsque la nature est documentée. Le type ne doit pas être déduit uniquement du nom de la variable.

## 7. Pilote INS RGPH 2024 — état réel

- Page thématique officielle identifiée.
- Fichier XLSX dédié et lien direct identifiés.
- Tentative de récupération du binaire dans l'environnement d'exécution échouée.
- Aucun chiffre par gouvernorat n'a été saisi ou reconstruit manuellement.
- Le modèle, le registre de source, le dictionnaire provisoire et le mécanisme d'import sont prêts à recevoir le fichier.
- L'alimentation de la vue Équité territoriale reste suspendue jusqu'à inspection du fichier, validation de son grain et mapping documenté.

Le premier cas d'usage est donc **opérationnel en démonstration synthétique uniquement, mais pas encore intégré sur données INS réelles**. La vue Équité affiche les 24 gouvernorats avec des valeurs générées, un avertissement explicite, `value_origin=synthetic_demo_only` et `reference_period=DEMO_ONLY_NOT_RGPH2024`. Elle n'affiche aucune valeur illustrative en mode REAL_DATA. Aucun chiffre synthétique ne doit être présenté comme issu du RGPH 2024.

## 8. Sécurité et gouvernance

Le pipeline Lot 1 bloque les classifications confidentielles et personnelles/sensibles, ainsi que les colonnes individuelles manifestes. Ce filtrage par nom de colonne ne remplace pas une revue de contenu ni un contrôle juridique. Les petits effectifs et risques de ré-identification devront être traités dans les règles de validation propres aux jeux.

Le rôle `analyst/admin` reste soumis au contexte d'authentification prévu en Lot 0. Aucun SSO institutionnel n'est raccordé dans cette tranche. Le partage de données, les licences, les conventions et les finalités doivent être approuvés par les propriétaires institutionnels.

## 9. Limites connues

- Streamlit n'est pas installé dans l'environnement d'audit : l'interface a été compilée statiquement, mais pas testée en session interactive.
- Le fichier XLSX INS n'a pas été téléchargé ; le mapping spécifique et la comparaison RGPH 2014–2024 ne sont pas réalisés.
- Les chargeurs métier du Data Warehouse et l'approbation de lot ne sont pas encore exposés.
- Les connecteurs HTTP/API institutionnels ne sont pas actifs ; seuls les imports fichiers sont opérationnels.
- L'architecture actuelle de sécurité n'est pas un dispositif institutionnel de production.

# TEDT — Mission 03 / Lot 1 — Étape B : modèle détaillé

## Décisions de conception retenues après validation de l'architecture

- SQLite dédié : `data/tedt_foundation.sqlite`, séparé de la base des scénarios.
- Fichiers originaux dans `data/staging/<batch_id>/`, manifeste et empreinte SHA-256.
- Import manuel CSV/XLSX en premier connecteur.
- UUID interne `tedt_institution_id` et `official_id` nullable ; aucun identifiant officiel fabriqué.
- Historisation bitemporelle simplifiée : validité métier (`valid_from`, `valid_to`) et enregistrement (`recorded_at`, `superseded_at`).
- Pas de fusion automatique des doublons ; mise en quarantaine à la charge des étapes de mapping.
- Dictionnaire d'indicateurs versionné par `(indicator_code, version)`.
- Faits séparés par grain ; toutes les observations gardent `source_id`, `batch_id` et `quality_status`.
- Aucun chargement automatique après import ; approbation métier explicite requise.
- Données personnelles et confidentielles exclues.

## Schémas de référence

Le DDL exécutable est `data/foundation/schema.sql`. Il crée les tables suivantes :

| Domaine | Tables |
|---|---|
| Sources et jeux | `source`, `dataset` |
| Ingestion et qualité | `ingestion_batch`, `validation_run`, `validation_issue`, `transformation_run` |
| Registre maître | `institution`, `institution_version`, `institution_alias`, `institution_relation` |
| Dimensions | `dim_period`, `dim_geography`, `dim_education_level`, `dim_sex`, `dim_milieu` |
| Dictionnaire | `indicator_dictionary` |
| Faits | `fact_enrolment`, `fact_staff`, `fact_infrastructure`, `fact_learning_outcome`, `fact_territorial_indicator`, `fact_expenditure`, `fact_observation` |

## Métadonnées obligatoires d'un lot

`source_id`, `dataset_code`, `source_owner`, `source_title`, `source_reference`, `reference_period_start`, `reference_period_end`, `geographic_level`, `granularity`, `declared_license_or_authorization`, `security_classification`, `language`, `schema_version`.

Le système ajoute : `batch_id`, `received_at`, `received_by`, `source_filename`, `stored_filename`, `sha256`, `file_size`, `file_format`, profil de variables et état.

## Statuts de traitement

`RECEIVED → PROFILED → VALIDATED → MAPPED → APPROVED → LOADED`

Alternatives : `REJECTED`, `QUARANTINED`, `SUPERSEDED`.

Le Lot 1 livré active jusqu'au contrôle structurel (`VALIDATED`). Le mapping métier, l'approbation et le chargement des faits restent des étapes ultérieures.

## Source pilote

INS — RGPH 2024 — Scolarisation 6–14 ans. Page INS officielle :
https://www.ins.tn/enquetes/recensement-general-de-la-population-et-de-lhabitat-2024-analyses-thematiques

Lien direct XLSX identifié :
https://ins.tn/sites/default/files-ftp3/files/2025-09/Scolarisation%20%286%20-%2014%20ans%29_Final.xlsx

État : fichier non récupéré dans l'environnement d'exécution. Aucun mapping ni résultat territorial n'est revendiqué.

## Démonstration territoriale en mode DEMONSTRATION

En l'absence du classeur INS dans l'environnement, un jeu séparé de 24 lignes est généré dans `data/demo/schooling_6_14_governorates_synthetic_demo.csv`. Toutes les lignes portent `value_origin=synthetic_demo_only` et `reference_period=DEMO_ONLY_NOT_RGPH2024`. Le module Équité affiche ce jeu uniquement en mode DEMONSTRATION, avec un avertissement visible. En mode REAL_DATA, cette vue ne présente aucune valeur illustrative.

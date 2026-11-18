# TEDT — Lot 1 : dossier de validation du modèle (Étape B)

Ce dossier accompagne `LOT1_ARCHITECTURE_NOTE.md`, `LOT1_SOURCE_REGISTER_DRAFT.csv` et `LOT1_INDICATOR_DICTIONARY_DRAFT.csv`.

## Décisions structurantes proposées

| Sujet | Proposition | Pourquoi |
|---|---|---|
| Entrepôt initial | SQLite distinct `data/tedt_foundation.sqlite` | Cohérent avec le prototype, simple à sauvegarder et tester |
| Fichiers bruts | `data/staging/<batch_id>/original.<ext>` + manifeste | Préserver les sources sans altération |
| Harmonisation | Python/Pandas + tables de correspondance versionnées | Réutilise la stack existante |
| Identifiant établissement | UUID interne `tedt_institution_id` + identifiant officiel nullable | Éviter les faux identifiants officiels |
| Historisation | Versions valides dans le temps et versions enregistrées | Suivre les changements et corriger sans écraser |
| Warehouse | Dimensions communes + faits au grain déclaré | Éviter les agrégations incompatibles |
| Indicateurs | Dictionnaire versionné central | Une seule formule par indicateur et version |
| Connecteur initial | CSV/XLSX manuel et générique | Aucun accès institutionnel n'est présumé |
| Cas pilote | INS RGPH 2024 — scolarisation 6–14 ans par gouvernorat | Source officielle identifiée, agrégats territoriaux pertinents |
| Temporalité | Comparaison RGPH 2014–2024 seulement après test de comparabilité | Ne pas fabriquer une tendance avec des définitions différentes |
| Données personnelles | Refusées au point d'entrée dans Lot 1 | Respect du périmètre et maîtrise des risques |

## Schéma d'import générique proposé

### Métadonnées minimales obligatoires du lot

`source_id`, `dataset_code`, `source_owner`, `source_title`, `source_url_or_reference`, `received_at`, `received_by`, `reference_period_start`, `reference_period_end`, `geographic_level`, `granularity`, `declared_license_or_authorization`, `security_classification`, `language`, `source_filename`, `sha256`, `schema_version`.

### Cycle de vie d'un lot

`RECEIVED → PROFILED → VALIDATED → MAPPED → APPROVED → LOADED`

États alternatifs : `REJECTED`, `QUARANTINED`, `SUPERSEDED`. Un rejet ou une quarantaine ne supprime jamais le fichier brut. Toute modification du mapping ou des règles produit une nouvelle version du traitement.

### Statuts de fiabilité

- `SOURCE_UNVERIFIED`: propriétaire ou droits non confirmés.
- `SOURCE_IDENTIFIED`: producteur et document source identifiés.
- `SOURCE_AUTHORIZED`: autorisation/licence enregistrée.
- `STRUCTURALLY_VALIDATED`: schéma et règles de validation réussis.
- `HARMONIZED`: nomenclatures et unités mappées.
- `INSTITUTIONALLY_CERTIFIED`: certification explicite par le propriétaire ou l'autorité compétente.

Ces statuts sont cumulatifs mais non interchangeables. Une validation structurelle ne certifie pas l'origine ni l'exactitude statistique.

## Questions à trancher pour la validation

1. Le stockage SQLite proposé convient-il au premier palier, avec possibilité d'évolution ultérieure vers PostgreSQL/DuckDB si les volumes le justifient ?
2. Le pilote INS RGPH 2024 sur la scolarisation des 6–14 ans par gouvernorat est-il validé comme premier cas d'usage ?
3. Confirme-t-on l'identifiant interne TEDT séparé de l'identifiant officiel, et l'absence de fusion automatique des doublons ?
4. Confirme-t-on la règle « aucun indicateur recalculé si formule, numérateur ou dénominateur ne sont pas documentés » ?
5. Confirme-t-on l'exclusion de toute donnée personnelle, confidentielle ou individuelle dans ce Lot 1 ?

**Aucun composant structurant du code ne sera développé avant validation de ces choix.**

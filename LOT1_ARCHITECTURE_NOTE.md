# TEDT — Mission 03 / Lot 1
## Note d'architecture proposée — Étape A

**Statut : architecture validée par l’utilisateur le 17 novembre 2026. Première tranche de développement Lot 1 engagée.**

## 1. Diagnostic de départ

L'archive Lot 0 a été réextraite dans un espace d'audit distinct. Résultats réexécutés : `72 passed`; compilation de `app.py`, `ui.py`, `tedt_core`, `views` et `tests` réussie.

Le prototype conserve huit vues Streamlit et un noyau `tedt_core`. `data_store.py` construit un `DataBundle` en mémoire contenant six familles (`context`, `institutions`, `results`, `exam_items`, `curriculum`, `students`). Les imports Lot 0 ne concernent que `institutions` et `results`. La validation porte sur des schémas techniques et métier, mais le stockage de staging, le registre d'établissements, le dictionnaire versionné d'indicateurs et le warehouse ne sont pas encore présents.

Le catalogue documentaire comporte 31 fiches, mais certaines références sont indirectes, anciennes ou insuffisamment vérifiées. Le dossier `data/official/` est vide. Les données synthétiques restent les seules données embarquées dans le mode DEMONSTRATION. La base SQLite existante est dédiée aux scénarios et doit rester distincte du futur entrepôt.

## 2. Principes d'architecture

1. **Conserver l'application et les huit modules.** Ajouter une couche de données en amont, ne pas réécrire les vues.
2. **Séparer les plans de données.** Les données brutes, les données harmonisées, l'entrepôt, les scénarios et les données synthétiques ont des espaces distincts.
3. **Immutabilité de l'import brut.** Chaque fichier reçu est conservé sans réécriture, identifié par SHA-256, date, source déclarée, utilisateur, licence/autorisation, période et couverture.
4. **Pas de promotion silencieuse.** Un fichier ne passe à l'état validé/harmonisé qu'après contrôles et approbation explicite.
5. **Provenance propagée.** Chaque observation de l'entrepôt conserve source, lot d'import, période, version de schéma, méthode de transformation et statut qualité.
6. **Aucun identifiant officiel inventé.** L'identifiant interne TEDT est technique et explicitement distinct de l'identifiant officiel fourni par le ministère.
7. **Aucune donnée individuelle dans Lot 1.** Import limité aux données publiques ou agrégées; contrôle de petits effectifs et de ré-identification à prévoir.
8. **Simplicité technologique.** Rester sur Python/Pandas/SQLite au premier palier. Évaluer DuckDB/Parquet uniquement si les volumes l'exigent; pas de serveur distribué ni de plateforme lourde à ce stade.

## 3. Architecture logique en six niveaux

| Niveau | Composants proposés | Règle de passage |
|---|---|---|
| Sources | Fichiers administratifs autorisés, publications INS, UIS, Banque mondiale, autres institutions | Fiche source et droits d'usage documentés |
| Staging | Fichier original en lecture seule, manifeste JSON, empreinte SHA-256, métadonnées de lot | Aucune altération du fichier reçu |
| Contrôle | Validation format, colonnes, types, domaines, doublons, géographie, temps, dénominateurs, petits effectifs | Rapport de validation et rejets conservés |
| Harmonisation | Nomenclatures, unités, périodes, clés, correspondances, transformations versionnées | Règles documentées et reproductibles |
| Warehouse | Dimensions partagées et faits agrégés historisés | Observations liées à une source, un lot et une version d'indicateur |
| Exploitation | Adaptateurs vers les huit modules existants, API interne de lecture | Modules lisent les données du mode actif, jamais les fichiers bruts directement |

## 4. Modèle de données cible (premier palier)

### 4.1 Métadonnées et pipeline

- `source`: institution productrice, nom, URL, type de source, contact, licence/conditions, statut d'accès.
- `dataset`: famille, schéma attendu, granularité, couverture géographique et temporelle, fréquence, classification de sécurité.
- `ingestion_batch`: identifiant de lot, source/dataset, fichier, SHA-256, taille, date de réception, acteur, autorisation déclarée, période, couverture, statut.
- `raw_artifact`: chemin du fichier original et format; fichier non modifié.
- `validation_run` et `validation_issue`: version des règles, compteurs, lignes/colonnes concernées, sévérité et motif.
- `transformation_run`: mapping versionné, colonnes source/cible, formule, paramètres, acteur, horodatage.

### 4.2 Référentiel maître des établissements

- `institution`: `tedt_institution_id` interne (UUID), `official_id` nullable, `official_id_issuer`, `id_status` (`official_verified`, `provisional_internal`, `unresolved`), type, statut courant.
- `institution_version`: nom, niveau, tutelle, statut, coordonnées, délégation, gouvernorat, dates de validité métier (`valid_from`, `valid_to`) et dates d'enregistrement (`recorded_at`, `superseded_at`), source et motif.
- `institution_alias`: anciens noms et variantes arabes/françaises, période, source.
- `institution_relation`: fusion, scission, remplacement, rattachement; entité source/cible, date et justification.
- `institution_identifier`: identifiants par système émetteur avec contrainte d'unicité par émetteur.

Aucune clé provisoire ne sera présentée comme officielle. Les doublons présumés sont mis en quarantaine; ils ne sont pas fusionnés automatiquement. Les changements d'adresse, de nom ou de tutelle créent une nouvelle version, pas une écrasement.

### 4.3 Dimensions et faits du warehouse

Dimensions partagées : `dim_period`, `dim_geography` (gouvernorat/délégation/secteur selon nomenclature disponible), `dim_institution`, `dim_source`, `dim_indicator`, `dim_education_level`, `dim_sex`, `dim_milieu`.

Faits séparés par grain :
- `fact_enrolment`: établissement × année scolaire × niveau × sexe (uniquement si source à ce grain).
- `fact_staff`: établissement/région × période × discipline/niveau (si autorisé et agrégé).
- `fact_infrastructure`: établissement × période × type d'équipement.
- `fact_learning_outcome`: territoire/établissement × période × cycle × matière × population d'examen.
- `fact_territorial_indicator`: territoire × période × indicateur × désagrégations publiées.
- `fact_expenditure`: exercice × programme/niveau/nature × territoire si cette désagrégation est publiée.

Chaque fait porte `source_id`, `batch_id`, `indicator_version_id`, `quality_status`, `loaded_at`; numérateur et dénominateur sont stockés séparément lorsqu'ils existent. Le grain d'une table est déclaré et testé pour empêcher les agrégations incompatibles.

## 5. Dictionnaire d'indicateurs

Un registre central versionné doit être l'unique autorité de calcul. Les vues ne définissent plus de formule locale. Champs : code, libellés FR/AR, type (ressource/processus/réalisation/résultat/impact), définition, objectif, formule, numérateur, dénominateur, unité, grain, désagrégations, périodicité, période, source, propriétaire, méthode, statut de fiabilité, limites, politique de valeurs manquantes, seuil de confidentialité, version et date d'effet.

Un indicateur dont la formule, le dénominateur ou le champ de validité n'est pas documenté est conservé comme **valeur publiée par la source**, sans recalcul indépendant. Les définitions provisoires ne sont pas promues en indicateurs certifiés.

## 6. Importation générique

Premier connecteur : CSV/XLSX, import manuel contrôlé. Le formulaire demande au minimum : source, propriétaire, nom du jeu, période, niveau géographique, granularité, licence/autorisation, classification, langue/nomenclature, description et contact. Le système détecte format, taille, colonnes, feuilles, types et encodage.

Pipeline : dépôt original → manifeste → profilage → validation → rapport/rejets → mapping approuvé → harmonisation → chargement transactionnel warehouse. Rejouer un lot avec le même SHA-256 et la même version de règles doit produire le même résultat. Un lot rejeté reste consultable et exportable; aucun chargement partiel silencieux.

Connecteurs futurs préparés comme interfaces (`FileConnector`, `HttpCsvConnector`, `UISConnector`), mais aucune connexion au système ministériel n'est supposée exister.

## 7. Qualité des données

Le tableau de bord distingue les dimensions suivantes : disponibilité (jeu attendu reçu ou non), complétude (cellules non manquantes), exactitude (contrôles de domaine et, seulement si possible, rapprochement externe), cohérence (règles inter-colonnes/temps/géo), actualité (retard par rapport à la périodicité), unicité (clés et doublons), traçabilité (métadonnées et lineage), interopérabilité (taux de valeurs mappées vers nomenclatures de référence).

Les scores restent séparés par dimension; aucun score composite ne doit masquer un défaut critique. Les valeurs nulles, zéro et non applicables sont distinctes. Toute correction est une transformation versionnée avec valeur d'origine conservée.

## 8. Sécurité et gouvernance

Classification : `PUBLIC`, `INSTITUTIONAL_NON_SENSITIVE`, `CONFIDENTIAL`, `PERSONAL_SENSITIVE`. Lot 1 accepte les deux premières catégories seulement, sous réserve des droits de réutilisation et de la validation des petits effectifs. Les fichiers confidentiels/personnels sont rejetés au point d'entrée.

La loi organique tunisienne n° 2004-63 du 27 juillet 2004 encadre les traitements de données personnelles. Le dispositif devra faire valider par les responsables institutionnels et, si nécessaire, l'INPDP les finalités, autorisations, échanges et obligations applicables. Une publication publique n'emporte pas automatiquement licence ouverte ni droit de réutilisation illimité.

## 9. Cas d'usage pilote proposé

**Indicateurs de scolarisation des 6–14 ans par gouvernorat — RGPH 2024 (INS).** L'INS met à disposition une page officielle RGPH 2024 et un fichier Excel intitulé « Scolarisation (6–14 ans) » dans les analyses thématiques. Un jeu INS RGPH 2014 « Nombre de scolarisés de 6 à 14 ans par gouvernorat, milieu et sexe » est également référencé.

Périmètre pilote initial : importer le fichier officiel RGPH 2024, préserver sa fiche source et son fichier brut, vérifier le schéma et les 24 gouvernorats, harmoniser les noms géographiques, publier uniquement les mesures effectivement contenues dans le fichier, documenter l'indicateur selon les métadonnées INS, puis alimenter une vue dédiée du module Équité territoriale.

Une comparaison 2014–2024 n'est autorisée qu'après contrôle de la comparabilité des définitions, populations de référence, unités et nomenclatures. Le PDF de synthèse seul ne suffit pas à reconstruire des valeurs exactes par gouvernorat à partir des classes de couleur d'une carte.

**Statut à ce stade : source officielle identifiée et fichier référencé; fichier binaire non encore intégré ni validé dans TEDT.** Il ne faut donc pas afficher ce pilote comme une intégration réelle achevée.

## 10. Décisions à valider avant développement

1. Confirmer SQLite comme premier entrepôt, séparé de `tedt_scenarios.sqlite`, avec staging immuable sur fichiers.
2. Confirmer l'identifiant interne TEDT UUID, strictement distinct de tout identifiant officiel.
3. Confirmer le cas pilote INS RGPH 2024 (scolarisation 6–14 ans par gouvernorat), comparaison 2014 conditionnelle.
4. Confirmer que les indicateurs non documentés restent des valeurs publiées non recalculées et non certifiées.
5. Confirmer que seuls les jeux publics/agrégés autorisés sont acceptés; aucun fichier individuel ou confidentiel.

Après validation, l'étape B détaillera les schémas SQL, le dictionnaire initial et la matrice des sources, puis le développement commencera par le pipeline d'importation et la traçabilité avant l'intégration des vues.

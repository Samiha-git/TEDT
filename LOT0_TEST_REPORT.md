# TEDT 2.0 — Lot 0 : rapport de tests avant/après

Date : 17 novembre 2026

## 1. Résultat global

| Mesure | Avant Lot 0 | Après Lot 0 |
|---|---:|---:|
| Tests existants | 49 | 49 conservés |
| Tests supplémentaires Lot 0 | 0 | 23 |
| Tests réussis | 49/49 | 72/72 |
| Tests échoués | 0 | 0 |
| Compilation Python | Baseline antérieure documentée | Réussie sur `app.py`, `ui.py`, `tedt_core`, `views`, `tests` |

Commande exécutée : `python -m pytest -q`

Résultat final : `72 passed`.

Commande de compilation : `python -m compileall -q app.py ui.py tedt_core views tests`

Résultat : aucune erreur de compilation.

## 2. Couverture des anomalies

| Anomalie | Correction livrée | Tests correspondants |
|---|---|---|
| C1 — Mélange réel/synthétique | Modes exclusifs ; aucun fallback synthétique en `REAL_DATA` ; provenance `synthetic`, `imported_unverified`, `unavailable` ; garde par module | `test_real_mode_never_fills_missing_datasets_with_synthetic`, `test_demo_mode_ignores_real_overrides`, `test_real_mode_revalidates_overrides_before_activation`, `test_real_mode_import_provenance_is_unverified_not_official`, `test_real_mode_accepts_only_validated_aggregate_imports` |
| C2 — Validation | Schémas, colonnes obligatoires/facultatives, score avec rétention, valeurs manquantes/invalides/non applicables, rejets exportables, doublons | `test_quality_score_penalizes_missing_optional_and_rejected_rows`, `test_missing_required_column_never_scores_full_completeness`, `test_missing_invalid_and_not_applicable_are_counted_separately`, `test_duplicate_column_names_are_rejected_without_crashing` |
| C3 — Imputation | Politique centralisée ; aucun remplacement implicite ; stratégie médiane uniquement explicite et auditée ; simulateur bloqué en présence de valeurs requises manquantes | `test_missing_policy_blocks_by_default_and_audits_explicit_median`, `test_median_imputation_rejects_invalid_non_numeric_values`, `test_simulation_blocks_missing_values_instead_of_imputing` |
| C4 — Agrégations cycle/année | Agrégations par cycle/année conservées ; taux de réussite pondéré uniquement par le nombre de candidats ; pas de taux global mélangeant les cycles | `test_result_school_year_and_subject_are_validated`, `test_governorate_aggregation_is_cycle_specific`, `test_governorate_coverage_is_explicit_and_never_assumes_national` et tests de validation existants |
| C5 — Identifiants/doublons | Rejet des identifiants d'établissement dupliqués ; détection des lignes identiques en l'absence d'identifiant officiel ; avertissement si identifiant absent | `test_duplicate_institution_ids_are_rejected` |
| C15 — Reproductibilité | Empreinte de données, graine Monte-Carlo, version moteur, hypothèses, provenance et acteur sauvegardés ; journal d'audit | `test_scenario_history_stores_reproducibility_metadata_and_audit` |
| C20 — Valeurs manquantes/PDF | Suppression de l'assimilation du décrochage manquant à zéro ; PDF exigeant des indicateurs complets ; gestion explicite des dépendances arabes | `test_french_pdf_export_produces_pdf_when_reportlab_available`, `test_arabic_pdf_dependency_failure_is_explicit` |
| C21 — Indicateurs | Moyenne pondérée commune sur paires observées ; Gini, Lorenz et écarts distributifs bloqués si valeurs manquantes | `test_distribution_metrics_reject_missing_data` et tests métriques initiaux |
| C24 — Traçabilité export | En-têtes mode/provenance/avertissement ajoutés aux exports analytiques CSV et métadonnées de provenance dans le PDF | `test_csv_export_has_mode_and_provenance_headers` |
| Sécurité — rôles/historique | Matrice viewer/analyst/admin, import et sauvegarde réels réservés aux rôles authentifiés, suppression UI retirée, permissions fichier et audit | `test_real_scenario_save_requires_authenticated_analyst_or_admin` et tests de persistance initiaux |

## 3. Vérification des deux modes

### DEMONSTRATION

- Six jeux sont présents : `institutions`, `results`, `exam_items`, `curriculum`, `students`, `context`.
- Leur provenance est `synthetic`.
- Les imports de session ne remplacent aucun jeu dans ce mode.
- Les graphiques affichent un filigrane « SYNTHETIC DEMONSTRATION · NOT OFFICIAL DATA ».

### REAL_DATA sans import institutionnel fourni

- Les six jeux sont marqués `unavailable`.
- Les tables `institutions` et `results` contiennent zéro ligne.
- Les modules dépendants sont bloqués, sauf l'Observatoire.
- Aucun générateur synthétique n'est appelé comme solution de repli.

### REAL_DATA avec import

Le chemin d'activation est codé et testé au niveau du noyau : validation, rejet des observations invalides, revalidation au moment de la construction du bundle et provenance `imported_unverified`. Aucun fichier officiel réel n'a été fourni pour cette mission ; aucun résultat réel n'est donc revendiqué.

L'interface bloque volontairement l'activation sans session authentifiée analyst/admin. Le raccordement OIDC/SSO n'est pas livré dans Lot 0.

## 4. Exports PDF et langues

- PDF français : génération réelle et vérification de la signature `%PDF` réussies avec ReportLab.
- PDF arabe : le chemin d'erreur est testé. `arabic-reshaper` et `python-bidi` ne sont pas installés dans l'environnement ; l'export arabe est donc annoncé comme indisponible au lieu de produire un document dont le façonnage RTL n'a pas été vérifié.
- Interface : les libellés français et arabes sont conservés ; les modules et vues sont compilés.

## 5. Limites d'exécution non levées

1. Streamlit n'est pas installé dans l'environnement d'audit et l'accès réseau aux paquets était indisponible. Le démarrage réel de l'application et les tests end-to-end interactifs des huit modules n'ont pas pu être exécutés.
2. Les dépendances de façonnage arabe du PDF ne sont pas installées ; seul le chemin d'indisponibilité arabe a été testé.
3. Aucun jeu de données institutionnel réel n'a été fourni. La validation des valeurs, des identifiants et des agrégations sur des sources tunisiennes officielles reste à réaliser avec les propriétaires des données.
4. L'authentification OIDC/SSO et le RBAC institutionnel sont préparés par contrat, mais non raccordés. Aucune donnée individuelle ou confidentielle ne doit être intégrée avant ce raccordement et l'audit de sécurité.
5. Les tests d'interface des huit modules ne sont pas remplacés par les tests unitaires : leur recette visuelle et fonctionnelle reste à réaliser dans un environnement équipé de Streamlit.

## 6. Conclusion de test

Les 49 tests initiaux sont conservés et réussis. Les 23 tests ajoutés passent. Les règles centrales de provenance, de validation, de calcul et de simulation sont couvertes par des tests automatisés.

Le Lot 0 peut être considéré comme validé au niveau du noyau métier et de la compilation. Il ne peut pas encore être déclaré prêt pour une mise en production institutionnelle, compte tenu des limites d'authentification, de l'absence de données officielles, de l'absence de tests end-to-end Streamlit et de la dépendance PDF arabe manquante.

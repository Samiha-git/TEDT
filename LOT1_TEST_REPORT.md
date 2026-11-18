# TEDT — Mission 03 / Lot 1 — Rapport de tests

## Résultats

| Mesure | Avant Lot 1 | Après première tranche Lot 1 |
|---|---:|---:|
| Tests existants | 72 | 72 conservés |
| Tests Lot 1 ajoutés | 0 | 14 |
| Total réussi | 72/72 | 86/86 |
| Échecs | 0 | 0 |
| Compilation Python | Réussie | Réussie |

Commandes :

- `python -m pytest -q` → `86 passed`.
- `python -m compileall -q app.py ui.py tedt_core views tests` → succès.

## Nouveaux tests

- création idempotente du schéma SQLite ;
- conservation des octets originaux et métadonnées ;
- empreinte SHA-256 ;
- refus des classifications personnelles ;
- refus de colonnes individuelles manifestes ;
- refus de source inconnue ;
- contrôle structurel et journalisation des anomalies ;
- séparation entre complétude calculable et dimensions de qualité inconnues ;
- rejet des colonnes obligatoires absentes ;
- statut explicite des identifiants provisoires ;
- unicité des identifiants officiels par émetteur ;
- chargement des registres de référence ;
- détection d'altération du fichier brut par SHA-256 ;
- jeu pilote synthétique explicitement non officiel, couvrant 24 gouvernorats et reproductible.

## Tests non exécutés

- démarrage Streamlit et parcours interactif de l'Observatoire : Streamlit absent de l'environnement ;
- import réel du classeur INS : binaire non récupéré ;
- recette métier des schémas du classeur INS : dépend de l'inspection du fichier ;
- chargement effectif des tables de faits et intégration au module Équité : en attente du mapping INS validé.

## Conclusion

Le socle de métadonnées, le staging, le contrôle structurel et le registre maître sont créés et testés au niveau du noyau Python. Cette tranche n'est pas une intégration de données réelles INS et ne constitue pas une mise en production institutionnelle.

# TEDT 2.0 — Démonstration des modes de données

Les exemples ci-dessous inspectent le noyau de données sans importer de données personnelles ni prétendre utiliser des observations officielles.

## 1. Mode DEMONSTRATION

```python
from tedt_core.data_store import build_bundle

bundle = build_bundle(mode="DEMONSTRATION")
print(bundle.mode)
print(bundle.provenance)
```

Résultat attendu :

- `mode = DEMONSTRATION`
- `institutions`, `results`, `exam_items`, `curriculum`, `students`, `context` portent tous la provenance `synthetic`.
- Les données d'un import utilisateur éventuel ne sont pas prises en compte dans ce mode.

## 2. Mode REAL_DATA sans jeu importé

```python
from tedt_core.data_store import build_bundle

bundle = build_bundle(mode="REAL_DATA")
print(bundle.provenance)
print(len(bundle.institutions), len(bundle.results))
```

Résultat attendu :

- Tous les jeux portent la provenance `unavailable`.
- Les effectifs de lignes des établissements et résultats sont nuls.
- Les modules dépendants affichent un blocage de données ; aucune donnée synthétique n'est injectée.

## 3. Chemin d'activation d'un fichier agrégé

```python
from tedt_core.data_store import build_bundle, validate_dataset

# df doit provenir d'un fichier agrégé fourni et autorisé par son propriétaire.
report = validate_dataset("institutions", df)
if not report.ok:
    raise ValueError(report.errors)

bundle = build_bundle(
    overrides={"institutions": report.clean},
    mode="REAL_DATA",
)
print(bundle.provenance["institutions"])
```

Le statut attendu est `imported_unverified` : le format et les règles métier ont été contrôlés, mais TEDT n'a pas certifié l'origine officielle du fichier.

Dans l'interface, l'activation de l'import est désactivée tant qu'une session authentifiée de rôle `analyst` ou `admin` n'est pas injectée par le futur fournisseur institutionnel OIDC/SSO.

## 4. Dépendances non disponibles en mode réel dans Lot 0

Les imports de cette phase ne couvrent que `institutions` et `results`. Les jeux `exam_items`, `curriculum`, `students` et `context` restent indisponibles en mode réel. Les modules Analyse des apprentissages et Alerte précoce sont donc bloqués ; le simulateur exige des indicateurs institutionnels complets et ne les impute pas.

Aucune donnée individuelle d'élève ou d'enseignant n'est importée dans cette mission.

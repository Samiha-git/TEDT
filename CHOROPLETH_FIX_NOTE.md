# Correctif TEDT — cartographie Équité

Cause : `ui.choropleth()` attendait `name_fr` ou `name_ar`, alors que le fichier de démonstration Lot 1 fournit `governorate_fr` et `governorate_ar`.

Correction : sélection du libellé géographique selon la langue avec solutions de repli ; vérification explicite des colonnes `governorate` et de la variable cartographiée ; construction du survol à partir des seules colonnes présentes.

Le code géographique `governorate` reste la clé de jointure avec le GeoJSON. Les autres vues et la séparation DEMONSTRATION / REAL_DATA ne sont pas modifiées.

Vérification effectuée : compilation Python réussie et sélection des colonnes françaises/arabe du fichier de démonstration vérifiée. L'interface Streamlit n'a pas été exécutée dans cet environnement.

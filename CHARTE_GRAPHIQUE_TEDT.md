# TEDT — Refonte de la charte graphique

Cette version applique la référence visuelle fournie par l'utilisatrice.

## Changements
- Fond clair bleu-gris, panneaux blancs/gris clair, cartes arrondies.
- Palette : bleu nuit `#0D1B2A`, bleu acier `#1B4F72`, turquoise `#0FA3A3`, vert `#20C997`, ambre `#F5A623`, fond `#F4F8FC`.
- Typographies : Poppins (titres), Inter (interface), Noto Sans Arabic (arabe), avec polices de repli.
- En-tête TEDT avec logotype original intégré en SVG.
- Logo du ministère sélectionné selon la langue : fichier français en interface FR, fichier arabe en interface AR.
- Mise à jour de la palette Plotly et des cartes géographiques via les couleurs de TEDT.

## Fichiers principaux modifiés
- `ui.py`
- `app.py`
- `tedt_core/config.py`
- `.streamlit/config.toml`
- `README.md`

## Ressources ajoutées
- `assets/branding/ministry_logo_fr.png`
- `assets/branding/ministry_logo_ar.png`

## Vérifications
- `compileall` : réussi.
- Tests : 85 réussis ; 1 test existant échoue dans cet environnement parce qu'il tente de modifier un fichier de staging volontairement rendu non modifiable. Ce test n'est pas lié aux changements graphiques.
- Streamlit n'est pas installé dans l'environnement d'exécution ; le rendu interactif doit être vérifié sur le poste local.

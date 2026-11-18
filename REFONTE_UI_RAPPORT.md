# TEDT — Refonte de l'interface (rapport)

## Principe
Seule la couche de présentation a été modifiée. `tedt_core/`, `data/` (sources, référentiels, base de scénarios), `assets/`, les tests existants : **inchangés** (vérifié par `diff` avec l'archive d'origine).

## Fichiers modifiés
| Fichier | Nature |
|---|---|
| `app.py` | `st.navigation(position="hidden")` (URLs inchangées) ; en-tête, barre de navigation, barre de paramètres, pied de page ; sidebar supprimée ; langue par défaut FR (était AR) |
| `ui.py` | CSS unique centralisé, icônes SVG, `brand_header`, `nav_bar`, `settings_bar`, `hero`, `panel`, `quick_access`, `page_title`, `footer`, `cards`/`card` (style KPI) ; `mode_selector` en liste déroulante (même clé `data_mode`, même callback) ; fonctions de données (`get_bundle`, `require_module_data`, `choropleth`, `style_fig`…) inchangées |
| `views/dashboard.py` | Bandeau d'accueil, KPI avec icônes, carte (gauche) + classement (droite) dans des cartes à titre bleu, accès rapides ; graphiques/analyses restantes conservés dans les onglets en dessous. Aucun calcul modifié |
| `views/{analytics,assistant,early_warning,equity,observatory,reports,simulation_lab}.py` | Une seule ligne : `st.title` → `ui.page_title` |
| `.streamlit/config.toml` | `toolbarMode = "minimal"` |
| `requirements.txt` | `streamlit>=1.52` (conteneurs horizontaux, `st.page_link(width=…)`, navigation `hidden`) |
| `tests/test_ui_refonte.py` | Nouveaux tests d'interface (ajout) |

## Tests
- Avant : 86 réussis. Après : **91 réussis** (86 + 5 nouveaux).
- Navigateur réel (Chromium/Playwright, Streamlit 1.67) : navigation entre les 8 modules en FR et en AR, 0 exception ; bascule FR→AR ; bascule vers « Données réelles » (module bloqué sans substitution synthétique, comportement d'origine) ; pas de débordement horizontal à 390 px.
- Captures dans `captures/`.

## Limites à connaître
- Dans l'environnement de test, Google Fonts est inaccessible : les captures utilisent les polices de repli, pas Poppins/Inter/Noto Sans Arabic (chargées normalement sur un poste connecté).
- Le graphique de droite est le **classement des gouvernorats** (donnée existante), pas une courbe d'évolution : le moteur ne fournit pas de série d'effectifs par année et rien n'a été inventé.
- Les 10 indicateurs existants du tableau de bord sont conservés en deux rangées de 5 cartes (la référence en montre 4).
- Les logos du ministère (fichiers du projet) ont un fond dégradé propre ; ils sont affichés tels quels.
- Les tests des exports PDF/CSV et de la persistance des scénarios sont ceux d'origine (verts) ; ils n'ont pas été re-testés manuellement dans le navigateur.

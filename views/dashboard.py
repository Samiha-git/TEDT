import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import ui
from tedt_core import data_store
from tedt_core.config import PALETTE, REFERENCE_AGGREGATES as REF, REFERENCE_SOURCE
from tedt_core.metrics import top_bottom_gap, weighted_gini, weighted_mean
from ui import L


def render():
    bundle = ui.get_bundle()
    ui.hero()
    ui.banner(bundle)

    level = st.radio(L("المرحلة", "Cycle"), ["all", "primary", "secondary"], horizontal=True, key="dash_level",
                     format_func=lambda v: L("الكل", "Tous") if v == "all" else ui.level_label(v))
    gov = bundle.governorates(None if level == "all" else level)
    P = gov["pupils"].to_numpy(float)

    # latest-year success indicator from results (if available)
    res = bundle.results
    last_year = int(res["year"].max())
    r = res[(res["year"] == last_year) & ((res["level"] == level) if level != "all" else True)]
    pass_rate = float("nan")
    # Enrolled pupils are not the denominator of an exam success rate.
    if level != "all" and {"pass_rate", "candidate_count"}.issubset(r.columns):
        valid = r["pass_rate"].notna() & r["candidate_count"].notna()
        if valid.all() and len(r) and r["governorate"].nunique() == len(data_store.GOVERNORATES):
            pass_rate = weighted_mean(r["pass_rate"], r["candidate_count"])
    def display(value, suffix=""):
        return f"{value:.1f}{suffix}" if pd.notna(value) else L("غير متاح", "Non disponible")

    cat = data_store.load_catalog()
    ready = data_store.readiness_index(cat)

    ui.cards([
        (L("عدد المؤسسات", "Établissements"), ui.fmt_int(gov["institutions"].sum()), ""),
        (L("عدد التلاميذ", "Élèves"), ui.fmt_int(gov["pupils"].sum()), ""),
        (L("عدد المدرسين", "Enseignants"), ui.fmt_int(gov["teachers"].sum()), ""),
        (L("متوسط حجم القسم", "Taille moyenne de classe"), f"{gov['pupils'].sum() / gov['classes'].sum():.1f}", L("تلميذ / قسم", "élèves / classe")),
        (L("تلميذ لكل مدرّس", "Élèves par enseignant"), f"{gov['pupils'].sum() / gov['teachers'].sum():.1f}", ""),
    ], icons=["school", "users", "book", "calc", "scale"], tones=["blue", "teal", "amber", "navy", "blue"])
    quality_ok = gov["quality"].notna().all()
    dropout_ok = gov["dropout"].notna().all()
    gini_q = weighted_gini(gov["quality"], P) if quality_ok else float("nan")
    ui.cards([
        (L("مؤشر جودة التعلمات (0-100)", "Indice de qualité des apprentissages (0-100)"), display(weighted_mean(gov["quality"], P) if quality_ok else float("nan")), L("اصطناعي · مرجّح بالتلاميذ", "synthétique · pondéré élèves") if ui.is_synthetic(bundle) else ""),
        (L(f"نسبة النجاح المتوسطة حسب المادة ({last_year})", f"Taux moyen de réussite par matière ({last_year})"), display(pass_rate * 100, "%"), L("مرجّح بعدد المترشحين لكل مادة", "pondéré par les candidats de chaque matière")),
        (L("نسبة التعثر/الانقطاع", "Taux de décrochage"), display(weighted_mean(gov["dropout"], P) * 100 if dropout_ok else float("nan"), "%"), ""),
        (L("الفوارق الجهوية (الفجوة بين الربع الأعلى والأدنى)", "Disparités régionales (écart quartile haut/bas)"), display(top_bottom_gap(gov["quality"], P) if quality_ok else float("nan")), L(f"نقاط جودة · جيني {gini_q:.3f}", f"points de qualité · Gini {gini_q:.3f}") if quality_ok else L("لا تتوفر بيانات الجودة", "Données de qualité indisponibles")),
        (L("الجاهزية الوثائقية للبيانات", "Préparation documentaire des données"), f"{ready:.0f}/100", L("من مصفوفة المصادر", "d'après la matrice des sources")),
    ], icons=["gauge", "percent", "alert", "scale", "db"], tones=["teal", "blue", "amber", "navy", "green"])

    options = {
        "institutions": (L("عدد المؤسسات", "Établissements"), False),
        "pupils": (L("عدد التلاميذ", "Élèves"), False),
        "class_size": (L("حجم القسم", "Taille de classe"), False),
        "ptr": (L("تلميذ لكل مدرّس", "Élèves par enseignant"), False),
        "equipment_index": (L("مؤشر التجهيز", "Indice d'équipement"), False),
        "quality": (L("جودة التعلمات", "Qualité des apprentissages"), False),
        "dropout": (L("نسبة الانقطاع", "Décrochage"), False),
    }
    options = {k: v for k, v in options.items() if k in gov.columns and gov[k].notna().any()}

    # Central zone: map (left) + statistical chart (right), each in a card with a title bar.
    col_map, col_rank = st.columns([5, 6])
    with col_map, ui.panel(L("التوزيع الترابي", "Répartition territoriale"), "pin", key="tedt-panel-map"):
        ind = st.selectbox(L("المؤشر", "Indicateur"), list(options), format_func=lambda k: options[k][0], key="dash_ind")
        fig = ui.choropleth(gov, ind, options[ind][0], hover={"pupils": L("التلاميذ", "Élèves")}, height=430)
        st.plotly_chart(fig, width="stretch")
        st.caption(L("حدود الولايات: geoBoundaries (CC BY 4.0). القيم: ", "Limites : geoBoundaries (CC BY 4.0). Valeurs : ") + (L("اصطناعية.", "synthétiques.") if ui.is_synthetic(bundle) else L("من الملف المستورد.", "du fichier importé.")))
    with col_rank, ui.panel(L("ترتيب الولايات", "Classement des gouvernorats"), "trend", key="tedt-panel-rank"):
        ind2 = st.selectbox(L("ترتيب حسب", "Classer par"), list(options), index=min(5, len(options)-1), format_func=lambda k: options[k][0], key="dash_rank")
        d = gov.sort_values(ind2, ascending=False)
        fig = px.bar(d, x=ui.name_col(), y=ind2, color_discrete_sequence=[PALETTE["blue"]], labels={ind2: options[ind2][0], ui.name_col(): ""})
        st.plotly_chart(ui.style_fig(fig, 430), width="stretch")

    pages = st.session_state.get("_tedt_pages")
    if pages:
        ui.quick_access([
            (pages["observatory"], L("استكشاف البيانات", "Explorer les données"), ":material/bar_chart:"),
            (pages["equity"], L("استكشاف الإنصاف الترابي", "Explorer l'équité territoriale"), ":material/balance:"),
            (pages["simulation"], L("محاكاة السيناريوهات", "Simuler des scénarios"), ":material/calculate:"),
            (pages["reports"], L("الاطلاع على التقارير", "Consulter les rapports"), ":material/description:"),
        ])

    # Remaining existing analyses (unchanged content), grouped below the main zone.
    st.markdown("&nbsp;", unsafe_allow_html=True)
    tab_inst, tab_rank, tab_ref = st.tabs([
        L("توزيع المؤسسات", "Distribution des établissements"), L("العلاقات", "Relations"), L("المرجع المنشور", "Référence publiée"),
    ])
    with tab_inst:
        inst = bundle.institutions if level == "all" else bundle.institutions[bundle.institutions["level"] == level]
        if {"lat", "lon"}.issubset(inst.columns) and inst[["lat", "lon"]].notna().all(axis=1).any():
            samp = inst.dropna(subset=["lat", "lon"]).sample(min(len(inst), 3000), random_state=0)
            # Fond de carte : contours des gouvernorats (présentation uniquement, aucune donnée ajoutée)
            outline = go.Choroplethmap(geojson=data_store.geojson(), locations=gov["governorate"], z=[0] * len(gov),
                                       featureidkey="properties.shapeName", colorscale=[[0, "#EAF2FA"], [1, "#EAF2FA"]], showscale=False,
                                       marker_line_width=0.9, marker_line_color="#9DB6CE", hoverinfo="skip")
            fig = go.Figure([outline, go.Scattermap(lat=samp["lat"], lon=samp["lon"], mode="markers", marker=dict(size=5, color=PALETTE["terracotta"], opacity=0.55),
                                          text=samp["governorate"].map(ui.gname), hovertemplate="%{text}<extra></extra>")])
            fig.update_layout(map=dict(style="white-bg", center=dict(lat=33.9, lon=9.6), zoom=5.1), height=520, margin=dict(l=0, r=0, t=10, b=0))
            ui.provenance_fig(fig)
            st.plotly_chart(fig, width="stretch")
            st.caption(L("مواقع تقريبية مولّدة حول مركز كل ولاية (عينة من 3000 مؤسسة كحد أقصى)؛ ليست إحداثيات حقيقية.", "Positions schématiques générées autour du centre de chaque gouvernorat (échantillon de 3 000 établissements max.) ; ce ne sont pas des coordonnées réelles."))
        else:
            st.info(L("الملف النشط لا يحتوي على إحداثيات (lat, lon).", "Le fichier actif ne contient pas de coordonnées (lat, lon)."))
        by = inst.groupby(["governorate", "level"]).size().reset_index(name="n")
        by["name"] = by["governorate"].map(ui.gname)
        by["level_lbl"] = by["level"].map(ui.level_label)
        fig2 = px.bar(by, x="name", y="n", color="level_lbl", color_discrete_sequence=[PALETTE["blue"], PALETTE["terracotta"]], labels={"n": L("المؤسسات", "Établissements"), "name": "", "level_lbl": ""})
        st.plotly_chart(ui.style_fig(fig2, 380), width="stretch")
    with tab_rank:
        if gov["deprivation_index"].notna().any() and quality_ok:
            need_is_proxy = "deprivation_index_source" in gov and (gov["deprivation_index_source"] == "derived_proxy").any()
            need_label = L("مؤشر حاجة مشتق (قيمة بديلة)" if need_is_proxy else "مؤشر الحرمان (سياق)", "Indice de besoin dérivé (proxy)" if need_is_proxy else "Indice de privation (contexte)")
            fig = px.scatter(gov, x="deprivation_index", y="quality", size="pupils", hover_name=ui.name_col(), color_discrete_sequence=[PALETTE["terracotta"]],
                             labels={"deprivation_index": need_label, "quality": L("الجودة", "Qualité")})
            st.plotly_chart(ui.style_fig(fig, 380), width="stretch")
        else:
            st.info(L("لا تتوفر بيانات سياقية/جودة صالحة لهذا التحليل.", "Données contextuelles/de qualité indisponibles pour cette analyse."))
        if ui.is_synthetic(bundle):
            st.caption(L("العلاقة بين الحرمان والجودة هنا **افتراض مدمج في مولّد البيانات** وليست نتيجة تجريبية.", "La relation privation-qualité est ici une **hypothèse intégrée au générateur**, pas un résultat empirique."))
    with tab_ref:
        if bundle.mode != "DEMONSTRATION":
            st.info(L("هذه المقارنة المرجعية مخصصة حصرياً لوضع العرض التوضيحي ولا تُستخدم مع البيانات الحقيقية.", "Cette comparaison de référence est réservée au mode démonstration et n’est pas utilisée avec des données réelles."))
            return
        st.markdown(L("أرقام وطنية منشورة للموسم 2026-2027 (للمقارنة بالبيانات الاصطناعية فقط).", "Agrégats nationaux publiés pour 2026-2027 (uniquement pour situer l'échelle des données synthétiques)."))
        syn_tot = bundle.institutions[["pupils", "teachers", "classes"]].sum()
        rows = [
            (L("المؤسسات", "Établissements"), REF["institutions_total"], len(bundle.institutions)),
            (L("التلاميذ", "Élèves"), REF["pupils_total"], int(syn_tot["pupils"])),
            (L("المدرسون", "Enseignants"), REF["teachers_total"], int(syn_tot["teachers"])),
            (L("الفصول", "Classes"), REF["classes_total"], int(syn_tot["classes"])),
        ]
        st.dataframe(pd.DataFrame(rows, columns=[L("المؤشر", "Indicateur"), L("منشور (تقدير صحفي)", "Publié (relais presse)"), L("المنصة (النشط)", "Plateforme (actif)")]), hide_index=True, width="stretch")
        st.caption(f"{REFERENCE_SOURCE['label']} — {REFERENCE_SOURCE['url']}")
        st.caption(REFERENCE_SOURCE["status"])

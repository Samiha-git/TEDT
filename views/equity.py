import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import ui
from tedt_core.config import PALETTE
from tedt_core.metrics import lorenz_curve, weighted_gini, weighted_mean
from tedt_core.foundation_demo import make_schooling_demo
from ui import L

IND = {
    "pupils": ("عدد التلاميذ", "Élèves", False),
    "institutions": ("عدد المؤسسات", "Établissements", False),
    "class_size": ("حجم القسم", "Taille de classe", False),
    "ptr": ("تلميذ لكل مدرّس", "Élèves par enseignant", False),
    "equipment_index": ("مؤشر التجهيز", "Indice d'équipement", False),
    "quality": ("جودة التعلمات", "Qualité des apprentissages", False),
    "dropout": ("الانقطاع", "Décrochage", False),
    "deprivation_index": ("مؤشر الحرمان (سياق)", "Indice de privation (contexte)", False),
}
# component, direction (+1: higher value = higher priority)
PRIORITY_COMPONENTS = {
    "deprivation_index": (+1, "الحرمان", "Privation"),
    "ptr": (+1, "تلميذ/مدرّس", "Élèves/enseignant"),
    "class_size": (+1, "حجم القسم", "Taille de classe"),
    "equipment_index": (-1, "نقص التجهيز", "Déficit d'équipement"),
    "quality": (-1, "ضعف الجودة", "Faible qualité"),
    "dropout": (+1, "الانقطاع", "Décrochage"),
}


def _norm(s: pd.Series) -> pd.Series:
    r = s.max() - s.min()
    return (s - s.min()) / r if r > 0 else s * 0


def render():
    bundle = ui.get_bundle()
    ui.page_title(L("الإنصاف الترابي", "Équité territoriale"), "map")
    ui.banner(bundle)
    gov = bundle.governorates()
    P = gov["pupils"].to_numpy(float)
    ind_labels = IND.copy()
    priority_components = PRIORITY_COMPONENTS.copy()
    available = [k for k in ind_labels if k in gov.columns and gov[k].notna().any()]
    need_is_proxy = "deprivation_index_source" in gov and (gov["deprivation_index_source"] == "derived_proxy").any()
    if need_is_proxy:
        ind_labels["deprivation_index"] = ("مؤشر حاجة مشتق (قيمة بديلة)", "Indice de besoin dérivé (proxy)", False)
        priority_components["deprivation_index"] = (+1, "الحاجة المشتقة", "Besoin dérivé")
    t1, t2, t3, t4, t5 = st.tabs([L("الخريطة التفاعلية", "Carte interactive"), L("مقارنة المناطق", "Comparer les régions"), L("الفجوات والتوزيع", "Écarts et distribution"), L("المناطق ذات الأولوية", "Zones prioritaires"), L("تجربة Lot 1", "Pilote Lot 1")])
    with t1:
        ind = st.selectbox(L("المؤشر", "Indicateur"), available, index=min(3, len(available)-1), format_func=lambda k: L(ind_labels[k][0], ind_labels[k][1]), key="eq_ind")
        rel = st.checkbox(L("عرض الفرق عن المتوسط الوطني (%)", "Afficher l'écart à la moyenne nationale (%)"), key="eq_rel")
        g = gov.copy()
        if rel:
            valid = g[ind].notna()
            m = weighted_mean(g.loc[valid, ind], P[valid.to_numpy()])
            g["_v"] = (g[ind] / m - 1) * 100
            fig = ui.choropleth(g, "_v", L("الفرق عن المتوسط %", "Écart à la moyenne %"), diverging=True, zmid=0, hover={ind: L(ind_labels[ind][0], ind_labels[ind][1])})
        else:
            fig = ui.choropleth(g, ind, L(ind_labels[ind][0], ind_labels[ind][1]), hover={"pupils": L("التلاميذ", "Élèves")})
        st.plotly_chart(fig, width="stretch")
    with t2:
        pick = st.multiselect(L("اختر من 2 إلى 6 ولايات", "Choisir 2 à 6 gouvernorats"), sorted(gov["governorate"]), default=list(gov.sort_values("ptr", ascending=False)["governorate"][:2]) + list(gov.sort_values("ptr")["governorate"][:2]), format_func=ui.gname, max_selections=6, key="eq_pick")
        choices = [k for k in ["class_size", "ptr", "equipment_index", "quality", "dropout", "deprivation_index"] if k in available]
        inds = st.multiselect(L("المؤشرات", "Indicateurs"), choices, default=choices[:5], format_func=lambda k: L(ind_labels[k][0], ind_labels[k][1]), key="eq_inds")
        if len(pick) >= 2 and inds:
            sub = gov[gov["governorate"].isin(pick)]
            long = sub.melt(id_vars=["governorate"], value_vars=inds, var_name="ind", value_name="v")
            long["ind_lbl"] = long["ind"].map(lambda k: L(ind_labels[k][0], ind_labels[k][1]))
            long["gname"] = long["governorate"].map(ui.gname)
            fig = px.bar(long, x="ind_lbl", y="v", color="gname", barmode="group", labels={"v": "", "ind_lbl": "", "gname": ""}, color_discrete_sequence=[PALETTE["blue"], PALETTE["terracotta"], PALETTE["olive"], PALETTE["gold"], PALETTE["grey"], PALETTE["blue_light"]])
            fig.update_yaxes(matches=None)
            st.plotly_chart(ui.style_fig(fig, 400), width="stretch")
            z = sub.set_index("governorate")[inds]
            nat = np.array([weighted_mean(gov.loc[gov[i].notna(), i], P[gov[i].notna().to_numpy()]) for i in inds])
            tab = (z / nat - 1) * 100
            tab.index = [ui.gname(k) for k in tab.index]
            tab.columns = [L(ind_labels[c][0], ind_labels[c][1]) for c in tab.columns]
            st.markdown(L("**الفرق عن المتوسط الوطني (%)**", "**Écart à la moyenne nationale (%)**"))
            st.dataframe(tab.round(1), width="stretch")
        else:
            st.info(L("اختر ولايتين على الأقل ومؤشراً واحداً.", "Choisissez au moins 2 gouvernorats et 1 indicateur."))
    with t3:
        gap_choices = [k for k in ["ptr", "class_size", "equipment_index", "quality", "dropout"] if k in available]
        ind3 = st.selectbox(L("مؤشر الفجوة", "Indicateur d'écart"), gap_choices, format_func=lambda k: L(ind_labels[k][0], ind_labels[k][1]), key="eq_gap")
        best_high = st.radio(L("الأفضل هو", "Le meilleur est"), ["low", "high"], format_func=lambda v: L("القيمة الأدنى", "la valeur la plus basse") if v == "low" else L("القيمة الأعلى", "la valeur la plus haute"), horizontal=True, key="eq_best")
        ref = gov[ind3].min() if best_high == "low" else gov[ind3].max()
        d = gov.assign(gap=(gov[ind3] - ref))
        d = d.sort_values("gap", ascending=(best_high == "high"))
        fig = px.bar(d, x=ui.name_col(), y="gap", color_discrete_sequence=[PALETTE["terracotta"]], labels={"gap": L("الفجوة عن الأفضل ولاية", "Écart au meilleur gouvernorat"), ui.name_col(): ""})
        st.plotly_chart(ui.style_fig(fig, 380), width="stretch")
        # Lorenz of teachers per pupil, weighted by pupils
        res_pp = (gov["teachers"] / gov["pupils"]).to_numpy()
        x, y = lorenz_curve(res_pp, P)
        gini = weighted_gini(res_pp, P)
        fig = go.Figure()
        fig.add_scatter(x=x, y=y, mode="lines+markers", name="Lorenz", line=dict(color=PALETTE["blue"]))
        fig.add_shape(type="line", x0=0, y0=0, x1=1, y1=1, line=dict(dash="dash", color=PALETTE["grey"]))
        fig.update_layout(xaxis_title=L("الحصة التراكمية من التلاميذ", "Part cumulée des élèves"), yaxis_title=L("الحصة التراكمية من المدرّسين", "Part cumulée des enseignants"), title=L(f"منحنى لورنز لتوزيع المدرّسين (جيني {gini:.3f})", f"Courbe de Lorenz des enseignants (Gini {gini:.3f})"))
        st.plotly_chart(ui.style_fig(fig, 380), width="stretch")
    with t4:
        st.caption(L("مؤشر الأولوية = مجموع مرجّح لمكوّنات معيارية (0-1) موجَّهة بحيث تعني القيمة الأعلى أولوية أكبر. الأوزان خيار سياسي يحدده المستخدم، لا نتيجة إحصائية.",
                     "Indice de priorité = somme pondérée de composantes normalisées (0-1), orientées pour que plus élevé = plus prioritaire. Les poids sont un choix de politique publique fixé par l'utilisateur, pas un résultat statistique."))
        cols = st.columns(3)
        weights = {}
        for i, (k, (_sgn, ar, fr)) in enumerate(priority_components.items()):
            weights[k] = cols[i % 3].slider(L(ar, fr), 0, 10, 5, key=f"eq_w_{k}")
        tot = sum(weights.values())
        if tot == 0:
            st.warning(L("حدّد وزناً واحداً على الأقل.", "Fixez au moins un poids non nul."))
            return
        usable = [k for k in priority_components if k in available and gov[k].notna().all() and weights[k] > 0]
        if not usable:
            st.warning(L("لا توجد مكوّنات مكتملة تسمح بحساب مؤشر الأولوية دون إسناد قيم بديلة.", "Aucune composante complète ne permet de calculer l'indice sans imputation."))
            return
        used_weight = sum(weights[k] for k in usable)
        score = sum(weights[k] * (_norm(gov[k]) if priority_components[k][0] > 0 else 1 - _norm(gov[k])) for k in usable) / used_weight
        excluded = sorted(set(priority_components) - set(usable))
        if excluded:
            st.warning(L("استُبعدت المكوّنات غير المكتملة: ", "Composantes incomplètes exclues : ") + ", ".join(excluded))
        out = gov.assign(priority=score).sort_values("priority", ascending=False)
        topn = st.slider(L("عدد الولايات ذات الأولوية", "Nombre de gouvernorats prioritaires"), 3, 12, 6, key="eq_topn")
        out["rank"] = range(1, len(out) + 1)
        out["is_top"] = out["rank"] <= topn
        st.plotly_chart(ui.choropleth(out, "priority", L("مؤشر الأولوية", "Indice de priorité"), hover={"rank": L("الرتبة", "Rang")}), width="stretch")
        show = out[["rank", ui.name_col(), "priority", "pupils", "ptr", "class_size", "equipment_index", "quality", "dropout"]].copy()
        show.columns = [L("الرتبة", "Rang"), L("الولاية", "Gouvernorat"), L("الأولوية", "Priorité"), L("التلاميذ", "Élèves"), L("تلميذ/مدرّس", "Él./ens."), L("حجم القسم", "Classe"), L("التجهيز", "Équip."), L("الجودة", "Qualité"), L("الانقطاع", "Abandon")]
        st.dataframe(show.round(3), hide_index=True, width="stretch")
        st.download_button(L("تنزيل الترتيب (CSV)", "Télécharger le classement (CSV)"), ui.export_frame(show, bundle, ("institutions",)), "tedt_priority_zones.csv", "text/csv", key="eq_dl")
        st.session_state["priority_top"] = list(out[out["is_top"]]["governorate"])
        st.caption(L("يمكن استعمال هذه القائمة كنطاق مستهدف في مختبر المحاكاة (زر «تطبيق المناطق ذات الأولوية»).", "Cette liste peut servir de périmètre ciblé dans le laboratoire de simulation (bouton « Appliquer les zones prioritaires »)."))

    with t5:
        st.subheader(L("تجربة تجريبية لمؤشر التمدرس 6–14 سنة", "Démonstration du futur indicateur de scolarisation 6–14 ans"))
        if bundle.mode != "DEMONSTRATION":
            st.warning(L("لا توجد بعد بيانات INS معتمدة لهذا المؤشر. لن تُعرض قيم توضيحية في وضع البيانات الحقيقية.",
                         "Aucune donnée INS validée n'est encore disponible pour cet indicateur. Aucune valeur illustrative n'est affichée en mode réel."))
        else:
            demo = make_schooling_demo()
            st.error(L("بيانات اصطناعية للتوضيح فقط — ليست بيانات INS، ولا تمثل قيماً حقيقية لسنة 2024، ولا تصلح للتحليل أو القرار.",
                        "DONNÉES SYNTHÉTIQUES DE DÉMONSTRATION — pas des données INS, ne représentent pas 2024 et ne sont pas utilisables pour l'analyse ou la décision."))
            fig = ui.choropleth(demo, "schooling_rate_demo_pct", L("Valeur illustrative synthétique (%)", "قيمة اصطناعية توضيحية (%)"))
            st.plotly_chart(fig, width="stretch")
            st.dataframe(demo[["governorate_fr", "governorate_ar", "age_band", "schooling_rate_demo_pct", "reference_period", "value_origin", "source_id"]], hide_index=True, width="stretch")
            st.download_button(L("تنزيل ملف العرض مع بيانات المصدر", "Exporter le jeu de démonstration et sa provenance"),
                               demo.to_csv(index=False).encode("utf-8-sig"),
                               "tedt_lot1_schooling_synthetic_demo.csv", "text/csv", key="eq_lot1_demo_download")
            st.caption(L("الهدف هو اختبار المسار الجغرافي واللغوي فقط. ستُستبدل هذه القيم بملف INS بعد استلامه والتحقق من تعريفاته وتفصيله.",
                         "Cette vue teste uniquement le parcours cartographique et bilingue. Les valeurs seront remplacées par le fichier INS après réception et validation de ses définitions et de sa granularité."))

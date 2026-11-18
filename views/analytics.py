import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import ui
from tedt_core import diagnostics as dg, data_store
from tedt_core.config import BLOOM_LEVELS, PALETTE, SUBJECTS
from tedt_core.metrics import weighted_mean
from ui import L


def _bloom_label(k: str) -> str:
    for key, ar, fr in BLOOM_LEVELS:
        if key == k:
            return L(ar, fr)
    return k


def render():
    bundle = ui.get_bundle()
    ui.page_title(L("تحليلات التعلمات", "Analyse des apprentissages"), "book")
    ui.banner(bundle)
    res = bundle.results
    gov_all = bundle.governorates()
    coverage = data_store.governorate_coverage(bundle.results)
    if not coverage["complete"]:
        st.warning(L(f"التغطية الجهوية للنتائج {coverage['observed']}/{coverage['expected']} ولاية؛ النتائج لا تمثل تقديراً وطنياً كاملاً.",
                     f"Couverture territoriale des résultats : {coverage['observed']}/{coverage['expected']} gouvernorats ; les résultats ne constituent pas une estimation nationale complète."))

    c1, c2, c3 = st.columns(3)
    level = c1.selectbox(L("المرحلة", "Cycle"), ["primary", "secondary"], format_func=ui.level_label, key="la_level")
    subjects = c2.multiselect(L("المواد", "Matières"), list(SUBJECTS), default=list(SUBJECTS), format_func=lambda s: L(*SUBJECTS[s]), key="la_subj")
    govs = c3.multiselect(L("الولايات (فارغ = كل الولايات)", "Gouvernorats (vide = tous)"), sorted(gov_all["governorate"]), format_func=ui.gname, key="la_govs")
    years = sorted(res["year"].unique())
    y0, y1 = st.select_slider(L("الفترة", "Période"), options=years, value=(years[0], years[-1]), key="la_years")

    f = res[(res["level"] == level) & res["subject"].isin(subjects) & res["year"].between(y0, y1)]
    if govs:
        f = f[f["governorate"].isin(govs)]
    if f.empty:
        st.info(L("لا توجد بيانات للاختيار الحالي.", "Aucune donnée pour la sélection."))
        return
    f = f.assign(w=f["candidate_count"] if "candidate_count" in f.columns else np.nan)

    t1, t2, t3, t4 = st.tabs([L("تطور النتائج", "Évolution"), L("المواد والولايات", "Matières et gouvernorats"), L("الامتحانات وتصنيف بلوم", "Examens et taxonomie de Bloom"), L("مقارنة بين سنتين", "Comparaison entre deux années")])
    with t1:
        agg = f.groupby(["year", "subject"]).apply(lambda x: weighted_mean(x["mean_score"], x["w"]), include_groups=False).reset_index(name="score") if f["w"].notna().all() else pd.DataFrame()
        if not agg.empty:
            agg["subject_lbl"] = agg["subject"].map(lambda s: L(*SUBJECTS[s]))
            fig = px.line(agg, x="year", y="score", color="subject_lbl", markers=True, labels={"score": L("متوسط الدرجة (0-100)", "Score moyen (0-100)"), "year": "", "subject_lbl": ""})
            st.plotly_chart(ui.style_fig(fig), width="stretch")
        else:
            st.warning(L("لا تتوفر أعداد المترشحين اللازمة لترجيح النتائج؛ لم يُحسب متوسط وطني.", "Les effectifs de candidats nécessaires à la pondération sont absents ; aucune moyenne nationale n'est calculée."))
        if {"pass_rate", "candidate_count"}.issubset(f.columns) and f[["pass_rate", "candidate_count"]].notna().all().all():
            pr = f.groupby("year").apply(lambda x: weighted_mean(x["pass_rate"], x["candidate_count"]), include_groups=False).reset_index(name="pass")
            fig = px.bar(pr, x="year", y="pass", color_discrete_sequence=[PALETTE["blue"]], labels={"pass": L("نسبة النجاح", "Taux de réussite"), "year": ""})
            fig.update_yaxes(tickformat=".0%")
            st.plotly_chart(ui.style_fig(fig, 300), width="stretch")
        else:
            st.info(L("لا يُعرض معدل النجاح المجمع دون مقام عدد المترشحين.", "Le taux de réussite agrégé n'est pas affiché sans dénominateur de candidats."))
    with t2:
        yr = st.selectbox(L("السنة", "Année"), sorted(f["year"].unique(), reverse=True), key="la_year_heat")
        h = f[f["year"] == yr].pivot_table(index="governorate", columns="subject", values="mean_score", aggfunc="mean")
        h.index = [ui.gname(k) for k in h.index]
        h.columns = [L(*SUBJECTS[c]) for c in h.columns]
        fig = px.imshow(h, aspect="auto", color_continuous_scale=[[0, "#EAF3F7"], [1, "#0B3E57"]], labels=dict(color=L("الدرجة", "Score")))
        st.plotly_chart(ui.style_fig(fig, 620), width="stretch")
    with t3:
        items, curr = bundle.exam_items, bundle.curriculum
        c1, c2 = st.columns(2)
        sub = c1.selectbox(L("المادة", "Matière"), list(SUBJECTS), format_func=lambda s: L(*SUBJECTS[s]), key="la_exam_subj")
        yrs_i = sorted(items["year"].unique(), reverse=True)
        yr_i = c2.selectbox(L("سنة الامتحان", "Année de l'examen"), yrs_i, key="la_exam_year")
        it = items[(items["subject"] == sub) & (items["year"] == yr_i)]
        pe = dg.bloom_distribution(it)
        pc = dg.curriculum_distribution(curr[curr["subject"] == sub])
        labels = [_bloom_label(k) for k in dg.BLOOM_KEYS]
        fig = go.Figure()
        fig.add_bar(x=labels, y=pe.values, name=L("الامتحان", "Examen"), marker_color=PALETTE["terracotta"])
        fig.add_bar(x=labels, y=pc.values, name=L("البرنامج", "Programme"), marker_color=PALETTE["blue"])
        fig.update_layout(barmode="group", yaxis_tickformat=".0%")
        st.plotly_chart(ui.style_fig(fig, 360), width="stretch")
        al = dg.alignment_index(pe, pc)
        ui.cards([
            (L("مؤشر المطابقة المعرفية", "Indice d'alignement cognitif"), f"{al:.2f}", L("1 = نفس التوزيع", "1 = même profil")),
            (L("متوسط المستوى المعرفي: الامتحان", "Niveau cognitif moyen : examen"), f"{dg.cognitive_demand(pe):.2f}", "1-6"),
            (L("متوسط المستوى المعرفي: البرنامج", "Niveau cognitif moyen : programme"), f"{dg.cognitive_demand(pc):.2f}", "1-6"),
        ])
        trend = []
        for y in sorted(items[items["subject"] == sub]["year"].unique()):
            trend.append((y, dg.alignment_index(dg.bloom_distribution(items[(items["subject"] == sub) & (items["year"] == y)]), pc)))
        tr = pd.DataFrame(trend, columns=["year", "alignment"])
        fig = px.line(tr, x="year", y="alignment", markers=True, labels={"alignment": L("المطابقة", "Alignement"), "year": ""}, color_discrete_sequence=[PALETTE["olive"]])
        st.plotly_chart(ui.style_fig(fig, 300), width="stretch")
        sr = it.groupby("bloom_level")["success_rate"].mean().reindex(dg.BLOOM_KEYS)
        fig = px.bar(x=labels, y=sr.values, labels={"x": "", "y": L("نسبة النجاح في الأسئلة", "Taux de réussite aux items")}, color_discrete_sequence=[PALETTE["gold"]])
        fig.update_yaxes(tickformat=".0%")
        st.plotly_chart(ui.style_fig(fig, 300), width="stretch")
        st.caption(L("المطابقة = 1 − المسافة الكلية بين توزيعين (مستوى معرفي فقط، لا تغطية المحتوى). أسئلة الامتحان وتصنيفها بيانات اصطناعية؛ التصنيف الآلي الحقيقي لأسئلة الامتحانات يتطلب ترميزاً بشرياً مُحكَّماً أولاً.",
                     "Alignement = 1 − distance en variation totale entre deux profils (niveau cognitif uniquement, pas la couverture des contenus). Items et classement synthétiques ; une classification réelle exige d'abord un codage humain contrôlé."))
    with t4:
        ya, yb = st.columns(2)
        a = ya.selectbox(L("السنة الأولى", "Année A"), years, index=0, key="la_cmp_a")
        b = yb.selectbox(L("السنة الثانية", "Année B"), years, index=len(years) - 1, key="la_cmp_b")
        base = res[(res["level"] == level) & res["subject"].isin(subjects)]
        if govs:
            base = base[base["governorate"].isin(govs)]
        if "candidate_count" in base.columns and base["candidate_count"].notna().all():
            ca = base[base["year"] == a].groupby("subject").apply(lambda x: weighted_mean(x["mean_score"], x["candidate_count"]), include_groups=False)
            cb = base[base["year"] == b].groupby("subject").apply(lambda x: weighted_mean(x["mean_score"], x["candidate_count"]), include_groups=False)
            cmp_ = pd.DataFrame({L("المادة", "Matière"): [L(*SUBJECTS[s]) for s in ca.index], str(a): ca.values, str(b): cb.reindex(ca.index).values})
            cmp_[L("الفرق", "Écart")] = cmp_[str(b)] - cmp_[str(a)]
            st.dataframe(cmp_.round(2), hide_index=True, width="stretch")
            fig = px.bar(cmp_, x=L("المادة", "Matière"), y=L("الفرق", "Écart"), color_discrete_sequence=[PALETTE["blue"]])
            st.plotly_chart(ui.style_fig(fig, 320), width="stretch")
        else:
            st.warning(L("لا تتوفر أعداد المترشحين؛ تمت إعاقة المقارنة الموزونة بين السنتين.", "Effectifs candidats indisponibles ; comparaison pondérée entre années bloquée."))
        st.caption(L("فروق السنوات في البيانات الاصطناعية ضجيج عشوائي مضاف عمداً؛ لا تُقرأ كاتجاهات.", "Dans les données synthétiques, les écarts entre années sont du bruit aléatoire ajouté volontairement ; à ne pas lire comme des tendances."))

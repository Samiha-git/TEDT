import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import ui
from tedt_core import early_warning as ew
from tedt_core.config import PALETTE
from ui import L

FEATURE_LABELS = {
    "ses_index": ("المستوى الاجتماعي-الاقتصادي", "Niveau socio-économique"),
    "absence_rate": ("نسبة الغياب", "Taux d'absence"),
    "repetitions": ("مرات الإعادة", "Redoublements"),
    "prior_score": ("النتيجة السابقة", "Résultat antérieur"),
    "class_size": ("حجم القسم", "Taille de classe"),
    "distance_km": ("المسافة إلى المؤسسة (كم)", "Distance à l'établissement (km)"),
    "rural": ("وسط ريفي", "Milieu rural"),
    "level": ("المرحلة", "Cycle"),
}


def _fl(name: str) -> str:
    base = name.split("_secondary")[0] if name.startswith("level") else name
    base = "level" if name.startswith("level") else name
    ar, fr = FEATURE_LABELS.get(base, (name, name))
    return L(ar, fr)


@st.cache_resource(show_spinner=False)
def _train(students: pd.DataFrame):
    return ew.train(students)


def render():
    bundle = ui.get_bundle()
    ui.page_title(L("نظام الإنذار المبكر", "Système d'alerte précoce"), "alert")
    ui.banner(bundle)
    st.info(L("**نموذج تنبؤي، لا سببي.** تُدرَّب الخوارزمية على سجلات تلاميذ **اصطناعية مجهولة** يُولَّد فيها الانقطاع بقاعدة معلنة (انظر README). النتائج توضّح سلسلة العمل (تدريب، معايرة، تجميع، مراجعة الإنصاف) ولا تُعدّ نتائج تجريبية عن تونس. تُعرض النتائج مجمّعة فقط مع إخفاء الخلايا الأقل من 30.",
              "**Modèle prédictif, non causal.** L'algorithme est entraîné sur des dossiers d'élèves **synthétiques et anonymes** dont l'abandon est généré par une règle déclarée (voir README). Les résultats illustrent la chaîne de travail (entraînement, calibration, agrégation, audit d'équité) et ne constituent pas des résultats empiriques sur la Tunisie. Seuls des résultats agrégés sont affichés, avec suppression des cellules < 30."))
    model = _train(bundle.students)

    ui.cards([
        (L("مساحة تحت المنحنى AUC (اختبار)", "AUC (test)"), f"{model.auc:.3f}", L("0.5 = عشوائي", "0,5 = hasard")),
        (L("خطأ Brier", "Score de Brier"), f"{model.brier:.3f}", L("أقل أفضل", "plus bas = mieux")),
        (L("نسبة الانقطاع في العيّنة", "Taux d'abandon dans l'échantillon"), f"{model.base_rate * 100:.1f}%", L("اصطناعي", "synthétique")),
    ])
    t1, t2, t3, t4, t5 = st.tabs([L("جودة النموذج", "Qualité du modèle"), L("العوامل المؤثرة", "Facteurs"), L("المخاطر المجمّعة", "Risque agrégé"), L("حساب ملف افتراضي", "Profil hypothétique"), L("مراجعة الإنصاف", "Audit d'équité")])
    with t1:
        c1, c2 = st.columns(2)
        fig = go.Figure(go.Scatter(x=model.roc["fpr"], y=model.roc["tpr"], mode="lines", line=dict(color=PALETTE["blue"]), name="ROC"))
        fig.add_shape(type="line", x0=0, y0=0, x1=1, y1=1, line=dict(dash="dash", color=PALETTE["grey"]))
        fig.update_layout(xaxis_title=L("معدل الإنذارات الكاذبة", "Taux de faux positifs"), yaxis_title=L("الاستدعاء", "Rappel"))
        c1.plotly_chart(ui.style_fig(fig, 340), width="stretch")
        cal = model.calibration
        fig = go.Figure()
        fig.add_scatter(x=cal["predicted"], y=cal["observed"], mode="markers+lines", marker=dict(color=PALETTE["terracotta"]), name=L("المعايرة", "Calibration"))
        mx = float(max(cal["predicted"].max(), cal["observed"].max()))
        fig.add_shape(type="line", x0=0, y0=0, x1=mx, y1=mx, line=dict(dash="dash", color=PALETTE["grey"]))
        fig.update_layout(xaxis_title=L("الخطر المتوقع", "Risque prédit"), yaxis_title=L("الملاحَظ", "Observé"))
        c2.plotly_chart(ui.style_fig(fig, 340), width="stretch")
        thr = st.slider(L("عتبة الإنذار", "Seuil d'alerte"), 0.02, 0.5, 0.10, 0.01, key="ew_thr")
        m = ew.threshold_metrics(model, thr)
        ui.cards([(L("نسبة المُنذَرين", "Part signalée"), f"{m['flagged_share'] * 100:.1f}%", ""), (L("الاستدعاء", "Rappel"), f"{m['recall'] * 100:.1f}%", ""), (L("الدقة", "Précision"), f"{m['precision'] * 100:.1f}%", "")])
    with t2:
        imp = model.importance.copy()
        imp["label"] = imp["feature"].map(_fl)
        fig = px.bar(imp.sort_values("importance"), x="importance", y="label", orientation="h", error_x="std", color_discrete_sequence=[PALETTE["blue"]],
                     labels={"importance": L("انخفاض AUC عند خلط المتغير", "Baisse d'AUC par permutation"), "label": ""})
        st.plotly_chart(ui.style_fig(fig, 380), width="stretch")
        coef = model.coefficients.copy()
        coef["label"] = coef["feature"].map(_fl)
        coef["direction"] = coef["std_coef"].map(lambda v: L("يرفع الخطر", "augmente le risque") if v > 0 else L("يخفض الخطر", "réduit le risque"))
        st.dataframe(coef[["label", "std_coef", "direction"]].rename(columns={"label": L("المتغير", "Variable"), "std_coef": L("المعامل المعياري", "Coef. standardisé"), "direction": L("الاتجاه", "Sens")}).round(3), hide_index=True, width="stretch")
        st.caption(L("الأهمية والمعاملات ارتباطية: لا تعني أن تغيير المتغير سيغيّر الانقطاع (يتطلب ذلك تصميماً سببياً). هنا ترتبط بالقاعدة التي ولّدنا بها البيانات.",
                     "Importance et coefficients sont associatifs : ils n'impliquent pas qu'agir sur la variable change l'abandon (cela exige un schéma causal). Ici ils reflètent la règle qui a généré les données."))
    with t3:
        agg = ew.aggregate_risk(model, bundle.students)
        agg["name"] = agg["governorate"].map(ui.gname)
        agg["risk_pct"] = agg["mean_risk"] * 100
        valid = agg.dropna(subset=["mean_risk"])
        if len(valid) < len(agg):
            st.warning(L(f"أُخفيت {len(agg) - len(valid)} ولاية/ولايات لضعف حجم الخلية (<{ew.MIN_CELL}).", f"{len(agg) - len(valid)} gouvernorat(s) masqué(s) : effectif < {ew.MIN_CELL}."))
        g = valid.rename(columns={"risk_pct": "risk"})
        gdf = bundle.governorates()[["governorate", "name_ar", "name_fr"]].merge(g[["governorate", "risk", "n"]], on="governorate", how="inner")
        st.plotly_chart(ui.choropleth(gdf, "risk", L("الخطر المتوقع %", "Risque prédit %"), hover={"n": L("حجم العيّنة", "Effectif")}), width="stretch")
        st.dataframe(valid.sort_values("risk_pct", ascending=False)[["name", "n", "risk_pct", "observed_rate"]].rename(columns={"name": L("الولاية", "Gouvernorat"), "n": L("العيّنة", "Effectif"), "risk_pct": L("الخطر المتوقع %", "Risque prédit %"), "observed_rate": L("الملاحَظ", "Observé")}).round(3), hide_index=True, width="stretch")
        st.caption(L("لا تعرض المنصة أي هوية فردية: الحد الأدنى للخلية 30.", "Aucune identité individuelle n'est affichée : cellule minimale de 30."))
    with t4:
        st.caption(L("ملف **افتراضي** يدخله المستخدم لفهم سلوك النموذج؛ ليس تلميذاً حقيقياً.", "Profil **hypothétique** saisi pour comprendre le comportement du modèle ; ce n'est pas un élève réel."))
        c1, c2, c3 = st.columns(3)
        profile = {
            "ses_index": c1.slider(L("المستوى الاجتماعي-الاقتصادي (معياري)", "Niveau socio-économique (standardisé)"), -3.0, 3.0, 0.0, 0.1, key="ew_ses"),
            "absence_rate": c1.slider(L("نسبة الغياب", "Taux d'absence"), 0.0, 0.5, 0.05, 0.01, key="ew_abs"),
            "repetitions": c2.slider(L("مرات الإعادة", "Redoublements"), 0, 2, 0, key="ew_rep"),
            "prior_score": c2.slider(L("النتيجة السابقة", "Résultat antérieur"), 0, 100, 55, key="ew_prior"),
            "class_size": c3.slider(L("حجم القسم", "Taille de classe"), 10, 45, 25, key="ew_cs"),
            "distance_km": c3.slider(L("المسافة (كم)", "Distance (km)"), 0.1, 30.0, 2.0, 0.1, key="ew_dist"),
            "rural": 1 if c3.checkbox(L("وسط ريفي", "Milieu rural"), key="ew_rural") else 0,
            "level": c2.selectbox(L("المرحلة", "Cycle"), ["primary", "secondary"], format_func=ui.level_label, key="ew_level"),
        }
        risk, contrib = ew.predict_profile(model, profile)
        ui.cards([(L("الخطر المتوقع", "Risque prédit"), f"{risk * 100:.1f}%", L(f"المتوسط في العيّنة {model.base_rate * 100:.1f}%", f"moyenne échantillon {model.base_rate * 100:.1f}%"))])
        contrib["label"] = contrib["feature"].map(_fl)
        fig = px.bar(contrib.sort_values("contribution_logit"), x="contribution_logit", y="label", orientation="h", color_discrete_sequence=[PALETTE["terracotta"]],
                     labels={"contribution_logit": L("المساهمة في لوغاريتم الأرجحية (مقابل المتوسط)", "Contribution au log-odds (vs. moyenne)"), "label": ""})
        st.plotly_chart(ui.style_fig(fig, 340), width="stretch")
    with t5:
        thr2 = st.slider(L("عتبة التدقيق", "Seuil d'audit"), 0.02, 0.5, 0.10, 0.01, key="ew_thr_audit")
        audit = ew.fairness_audit(model, thr2)
        st.dataframe(audit.round(3), hide_index=True, width="stretch")
        st.caption(L("الجنس **ليس** مدخلاً في النموذج لكنه يُدقَّق. الفروق الكبيرة في الاستدعاء أو الإنذارات الكاذبة بين المجموعات إشارة تستوجب مراجعة بشرية قبل أي استعمال. غياب فرق هنا لا يضمن الإنصاف على بيانات حقيقية.",
                     "Le sexe n'est **pas** une variable d'entrée mais il est audité. De grands écarts de rappel ou de faux positifs entre groupes appellent une revue humaine avant tout usage. L'absence d'écart ici ne garantit pas l'équité sur des données réelles."))

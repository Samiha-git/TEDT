from dataclasses import asdict
import hashlib

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import ui
from tedt_core import scenario_store, security
from tedt_core import simulation as sim
from tedt_core.config import PALETTE
from ui import L

DEFAULTS = {"sim_x": 0, "sim_t": 0.0, "sim_b": 0, "sim_lam": 0, "sim_scope": [], "sim_preset": "central",
            "asm_eps_class": 10.0, "asm_eps_ptr": 6.0, "asm_eps_equip": 8.0, "asm_gamma": 0.5, "asm_kappa": 0.10, "asm_equip_k": 0.10,
            "asm_cost_t": 1.0, "asm_cost_room": 3.0, "asm_horizon": 5, "asm_tnd": 0.0}


def _init():
    for k, v in DEFAULTS.items():
        st.session_state.setdefault(k, v)


def _set(**kw):
    for k, v in kw.items():
        st.session_state[k] = v


def _reset():
    _set(sim_x=0, sim_t=0.0, sim_b=0, sim_lam=0, sim_scope=[])


def _apply_priority():
    _set(sim_scope=st.session_state.get("priority_top", []))


def render():
    _init()
    bundle = ui.get_bundle()
    gov = bundle.governorates()
    ui.page_title(L("مختبر محاكاة السياسات", "Laboratoire de simulation des politiques"), "flask")
    ui.banner(bundle)
    if "deprivation_index_source" in gov and (gov["deprivation_index_source"] == "derived_proxy").any():
        st.warning(L("مؤشر الحاجة المستخدم مشتق حسابياً من التجهيز والجودة والانقطاع؛ ليس مؤشراً رسمياً أو قياساً مستقلاً للفقر.", "L'indice de besoin utilisé est un proxy calculé à partir de l'équipement, de la qualité et du décrochage ; ce n'est ni un indicateur officiel ni une mesure indépendante de pauvreté."))
    st.caption(L("سياسة القيم المفقودة: لا تعويض تلقائي؛ أي متغير إلزامي ناقص يوقف المحاكاة.", "Valeurs manquantes : aucune imputation automatique ; toute variable obligatoire manquante bloque la simulation."))
    st.error(L(
        "**طبيعة النتائج: محاكاة حسابية مبسّطة، وليست تقديراً إحصائياً معايَراً.** المعادلات معلنة أدناه، لكن معاملات التأثير قيم افتراضية قابلة للتعديل ولم تُقدَّر على بيانات تونسية حقيقية. الأرقام تُظهر منطق السيناريو وحجم الكلفة النسبية، ولا تُقرأ كتوقعات.",
        "**Nature des résultats : simulation arithmétique simplifiée, pas une estimation statistique calibrée.** Les équations sont déclarées ci-dessous mais les coefficients d'effet sont des valeurs par défaut modifiables, non estimées sur des données tunisiennes réelles. Les chiffres montrent la logique du scénario et l'ordre de grandeur relatif des coûts ; ils ne doivent pas être lus comme des prévisions."))

    left, right = st.columns([1, 2], gap="large")
    with left:
        st.subheader(L("فرضيات السيناريو", "Hypothèses du scénario"))
        b1, b2 = st.columns(2)
        b3, b4 = st.columns(2)
        b1.button(L("إعادة ضبط", "Réinitialiser"), on_click=_reset, key="sim_btn_reset", width="stretch")
        b2.button(L("تخفيف الاكتظاظ −10%", "Classes −10 %"), on_click=lambda: _set(sim_x=10, sim_t=0.0, sim_b=0, sim_lam=0, sim_scope=[]), key="sim_btn_p1", width="stretch")
        b3.button(L("تجهيز موجَّه للحاجة", "Équipement ciblé"), on_click=lambda: _set(sim_x=0, sim_t=0.0, sim_b=5000, sim_lam=100, sim_scope=[]), key="sim_btn_p2", width="stretch")
        b4.button(L("مدرّسون إضافيون +3%", "Enseignants +3 %"), on_click=lambda: _set(sim_x=0, sim_t=3.0, sim_b=0, sim_lam=70, sim_scope=[]), key="sim_btn_p3", width="stretch")
        st.slider(L("تخفيض حجم القسم (%)", "Réduction de la taille des classes (%)"), 0, 40, key="sim_x", help=L("يُنشئ أقساماً ومدرّسين إضافيين بنسبة مدرّس/قسم ثابتة.", "Crée des classes et enseignants supplémentaires à ratio enseignant/classe constant."))
        st.slider(L("مدرّسون إضافيون (% من المخزون الوطني)", "Enseignants supplémentaires (% du stock national)"), 0.0, 10.0, step=0.5, key="sim_t", help=L("مدرّسون مساندون يخفضون نسبة تلميذ/مدرّس دون تغيير عدد الأقسام.", "Enseignants d'appui : réduisent élèves/enseignant sans changer le nombre de classes."))
        st.slider(L("ميزانية التجهيز (وحدات كلفة)", "Budget d'équipement (unités de coût)"), 0, 20000, step=500, key="sim_b", help=L("وحدة الكلفة = كلفة مدرّس لسنة واحدة. نفقة مرة واحدة.", "Unité de coût = coût d'un enseignant pendant un an. Dépense unique."))
        st.slider(L("وزن الإنصاف في توزيع الموارد (%)", "Poids d'équité dans la répartition (%)"), 0, 100, step=10, key="sim_lam", help=L("0 = حسب عدد التلاميذ، 100 = حسب الحاجة (التلاميذ × مؤشر الحرمان).", "0 = au prorata des élèves, 100 = selon le besoin (élèves × indice de privation)."))
        st.multiselect(L("الولايات المعنية (فارغ = كل الولايات)", "Gouvernorats concernés (vide = tous)"), sorted(gov["governorate"]), format_func=ui.gname, key="sim_scope")
        pt = st.session_state.get("priority_top")
        if pt:
            st.button(L("تطبيق المناطق ذات الأولوية", "Appliquer les zones prioritaires"), on_click=_apply_priority, key="sim_btn_prio")
        with st.expander(L("الافتراضات والمعاملات (قابلة للتعديل)", "Hypothèses et paramètres (modifiables)")):
            st.radio(L("مقياس شدة التأثير", "Échelle d'intensité des effets"), ["prudent", "central", "optimistic"], key="sim_preset", horizontal=True,
                     format_func=lambda k: {"prudent": L("حذر ×0.5", "Prudent ×0,5"), "central": L("مركزي ×1", "Central ×1"), "optimistic": L("متفائل ×1.5", "Optimiste ×1,5")}[k])
            st.number_input(L("نقاط جودة لكل وحدة لوغاريتمية من تخفيض حجم القسم", "Points de qualité par unité log de réduction de la taille de classe"), 0.0, 50.0, step=0.5, key="asm_eps_class")
            st.number_input(L("... من خفض تلميذ/مدرّس", "... de réduction d'élèves/enseignant"), 0.0, 50.0, step=0.5, key="asm_eps_ptr")
            st.number_input(L("... لكل +1.0 في مؤشر التجهيز", "... par +1,0 d'indice d'équipement"), 0.0, 50.0, step=0.5, key="asm_eps_equip")
            st.number_input(L("تضخيم الأثر مع الحاجة (γ)", "Amplification selon le besoin (γ)"), 0.0, 2.0, step=0.1, key="asm_gamma")
            st.number_input(L("مرونة الانقطاع (κ لكل 10 نقاط)", "Élasticité de l'abandon (κ par 10 points)"), 0.0, 1.0, step=0.01, key="asm_kappa")
            st.number_input(L("سرعة تشبّع التجهيز (k)", "Vitesse de saturation de l'équipement (k)"), 0.0, 1.0, step=0.01, key="asm_equip_k")
            st.number_input(L("كلفة مدرّس/سنة (وحدة كلفة)", "Coût enseignant/an (unité de coût)"), 0.1, 10.0, step=0.1, key="asm_cost_t")
            st.number_input(L("كلفة قسم جديد (وحدة كلفة، دفعة واحدة)", "Coût d'une nouvelle classe (unités de coût, une fois)"), 0.0, 50.0, step=0.5, key="asm_cost_room")
            st.number_input(L("أفق الكلفة (سنوات)", "Horizon des coûts (années)"), 1, 20, key="asm_horizon")
            st.number_input(L("اختياري: كلفة وحدة الكلفة بالدينار (0 = غير مُدخلة)", "Optionnel : valeur d'une unité de coût en dinars (0 = non renseignée)"), 0.0, 1e7, step=1000.0, key="asm_tnd")
            st.caption(L("القيم الافتراضية للمعاملات والكلفة **افتراضات توضيحية** ولا تمثل مصدراً رسمياً. لا أسعار ولا عروض تجارية مُدرجة.", "Les valeurs par défaut des coefficients et des coûts sont des **hypothèses illustratives**, sans source officielle. Aucun prix ni offre commerciale n'est inclus."))

    s = st.session_state
    scenario = sim.Scenario(class_size_reduction=s.sim_x / 100, extra_teachers_pct=s.sim_t, equipment_budget_um=float(s.sim_b), equity_weight=s.sim_lam / 100, scope=tuple(s.sim_scope) or None)
    asm = sim.Assumptions(eps_class=s.asm_eps_class, eps_ptr=s.asm_eps_ptr, eps_equip=s.asm_eps_equip, gamma_disadv=s.asm_gamma, kappa_dropout=s.asm_kappa,
                          equip_k=s.asm_equip_k, cost_teacher_um=s.asm_cost_t, cost_room_um=s.asm_cost_room, horizon_years=int(s.asm_horizon), teacher_cost_tnd=s.asm_tnd).scaled(sim.PRESETS[s.sim_preset])
    result = sim.run_scenario(gov, scenario, asm)
    mc_seed = 7
    mc = sim.monte_carlo(gov, scenario, asm, n=1000, seed=mc_seed)
    source_fingerprint = hashlib.sha256(pd.util.hash_pandas_object(gov.sort_values("governorate"), index=True).values.tobytes()).hexdigest()
    n, c = result.national, result.costs
    st.session_state["last_sim"] = {"national": n, "costs": c, "scenario": asdict(scenario), "mc": mc}

    with right:
        if "baseline" in result.warnings:
            st.info(L("لا تغيير في الفرضيات بعد: حرّك أحد الأشرطة أو اختر سيناريو جاهزاً.", "Aucune hypothèse modifiée : déplacez un curseur ou choisissez un scénario prédéfini."))
        if "class_size_extrapolation" in result.warnings:
            st.warning(L("تخفيض حجم القسم > 30% خارج المدى المعتاد للمعاملات: تفسير النتائج يتطلب حذراً مضاعفاً.", "Réduction de la taille de classe > 30 % : hors du domaine usuel des coefficients, interpréter avec une prudence accrue."))
        st.subheader(L("الأثر على الجودة والإنصاف", "Effets sur la qualité et l'équité"))
        ui.cards([
            (L("جودة التعلمات", "Qualité"), f"{n['quality_after']:.2f}", f"{L('قبل', 'avant')} {n['quality_before']:.2f} · Δ {n['delta_quality']:+.2f}"),
            (L("الانقطاع", "Abandon"), f"{n['dropout_after'] * 100:.2f}%", f"{L('قبل', 'avant')} {n['dropout_before'] * 100:.2f}% · {n['delta_dropout_rel'] * 100:+.1f}%"),
            (L("فجوة الأرباع (جودة)", "Écart quartiles (qualité)"), f"{n['gap_after']:.2f}", f"{L('قبل', 'avant')} {n['gap_before']:.2f}"),
            (L("جيني (جودة)", "Gini (qualité)"), f"{n['gini_quality_after']:.4f}", f"{L('قبل', 'avant')} {n['gini_quality_before']:.4f}"),
        ])
        ui.cards([
            (L("حجم القسم", "Taille de classe"), f"{n['class_size_after']:.2f}", f"{L('قبل', 'avant')} {n['class_size_before']:.2f}"),
            (L("تلميذ/مدرّس", "Élèves/enseignant"), f"{n['ptr_after']:.2f}", f"{L('قبل', 'avant')} {n['ptr_before']:.2f}"),
            (L("التجهيز", "Équipement"), f"{n['equipment_after']:.3f}", f"{L('قبل', 'avant')} {n['equipment_before']:.3f}"),
        ])
        st.subheader(L("الكلفة (وحدات كلفة = كلفة مدرّس لسنة)", "Coût (unités de coût = un enseignant-année)"))
        cost_cards = [
            (L("مدرّسون مضافون", "Enseignants ajoutés"), ui.fmt_int(c["teachers_added"]), ""),
            (L("أقسام مضافة", "Classes ajoutées"), ui.fmt_int(c["classrooms_added"]), ""),
            (L("كلفة جارية/سنة", "Coût récurrent/an"), ui.fmt_int(c["recurring_um_per_year"]), ""),
            (L("كلفة لمرة واحدة", "Coût unique"), ui.fmt_int(c["oneoff_um"]), ""),
            (L(f"المجموع على {c['horizon_years']} سنوات", f"Total sur {c['horizon_years']} ans"), ui.fmt_int(c["horizon_total_um"]), (f"≈ {ui.fmt_int(c['horizon_total_tnd'])} TND" if "horizon_total_tnd" in c else "")),
        ]
        ui.cards(cost_cards)
        if c["um_per_quality_point"] == c["um_per_quality_point"]:
            st.caption(L(f"كلفة كل نقطة جودة وطنية إضافية: {c['um_per_quality_point']:,.0f} وحدة كلفة (على الأفق المحدد، حسب المعاملات الحالية).", f"Coût par point de qualité nationale gagné : {c['um_per_quality_point']:,.0f} unités de coût (sur l'horizon choisi, avec les coefficients actuels)."))

        q = mc["delta_quality"]
        st.markdown(L(
            f"**نطاق عدم اليقين في المعاملات** (1000 سحب، كل معامل تأثير موزَّع بانتظام بين 0 وضعف قيمته): تغيّر الجودة الوطنية **{q['p10']:+.2f} ← {q['p90']:+.2f}** (الوسيط {q['p50']:+.2f}) نقطة. تغيّر الانقطاع النسبي: {mc['delta_dropout_rel']['p10'] * 100:+.1f}% ← {mc['delta_dropout_rel']['p90'] * 100:+.1f}%. ليس فاصل ثقة.",
            f"**Plage d'incertitude sur les paramètres** (1 000 tirages, chaque coefficient d'effet tiré uniformément entre 0 et deux fois sa valeur) : variation de qualité nationale **{q['p10']:+.2f} → {q['p90']:+.2f}** (médiane {q['p50']:+.2f}) point. Variation relative de l'abandon : {mc['delta_dropout_rel']['p10'] * 100:+.1f} % → {mc['delta_dropout_rel']['p90'] * 100:+.1f} %. Ce n'est pas un intervalle de confiance."))

    t1, t2, t3, t4, t5 = st.tabs([L("الخريطة", "Carte"), L("الولايات", "Gouvernorats"), L("الحساسية", "Sensibilité"), L("المعادلات", "Équations"), L("سجل السيناريوهات", "Historique")])
    gdf = result.gov
    with t1:
        what = st.radio(L("عرض", "Afficher"), ["delta_quality", "added_teachers", "equipment_budget_um", "cost_horizon_um"], horizontal=True, key="sim_map_what",
                        format_func=lambda k: {"delta_quality": L("تغيّر الجودة", "Variation de qualité"), "added_teachers": L("مدرّسون مضافون", "Enseignants ajoutés"), "equipment_budget_um": L("ميزانية التجهيز", "Budget d'équipement"), "cost_horizon_um": L("الكلفة الكلية", "Coût total")}[k])
        st.plotly_chart(ui.choropleth(gdf, what, what, hover={"quality": L("الجودة قبل", "Qualité avant"), "quality_after": L("الجودة بعد", "Qualité après")}), width="stretch")
    with t2:
        d = gdf.sort_values("delta_quality", ascending=False)
        fig = go.Figure()
        fig.add_bar(x=d[ui.name_col()], y=d["quality"], name=L("قبل", "Avant"), marker_color=PALETTE["blue_light"])
        fig.add_bar(x=d[ui.name_col()], y=d["quality_after"], name=L("بعد", "Après"), marker_color=PALETTE["blue"])
        fig.update_layout(barmode="group")
        fig.update_yaxes(range=[max(0, d["quality"].min() - 8), min(100, d["quality_after"].max() + 3)])
        st.plotly_chart(ui.style_fig(fig, 380), width="stretch")
        cols = ["governorate", "pupils", "class_size", "class_size_after", "ptr", "ptr_after", "equipment_index", "equipment_after", "quality", "quality_after", "delta_quality", "dropout", "dropout_after", "added_teachers", "added_classrooms", "equipment_budget_um", "cost_horizon_um"]
        out = gdf[cols].copy()
        out.insert(1, "name", gdf[ui.name_col()])
        st.dataframe(out.round(3), hide_index=True, width="stretch")
        st.download_button(L("تنزيل نتائج الولايات (CSV)", "Télécharger les résultats par gouvernorat (CSV)"), ui.export_frame(out, bundle, ("institutions",)), "tedt_scenario_governorates.csv", "text/csv", key="sim_dl")
    with t3:
        sens = sim.sensitivity(gov, scenario, asm)
        label = {"eps_class": L("أثر حجم القسم", "Effet taille de classe"), "eps_ptr": L("أثر تلميذ/مدرّس", "Effet élèves/enseignant"), "eps_equip": L("أثر التجهيز", "Effet équipement"), "gamma_disadv": L("تضخيم الحاجة", "Amplification besoin")}
        sens["label"] = sens["parameter"].map(label)
        fig = go.Figure()
        fig.add_bar(y=sens["label"], x=sens["at_zero"] - sens["central"], orientation="h", name=L("المعامل = 0", "Paramètre = 0"), marker_color=PALETTE["terracotta"])
        fig.add_bar(y=sens["label"], x=sens["at_double"] - sens["central"], orientation="h", name=L("المعامل ×2", "Paramètre ×2"), marker_color=PALETTE["olive"])
        fig.update_layout(barmode="overlay", xaxis_title=L("تغيّر في الجودة الوطنية مقارنة بالقيمة المركزية", "Variation de la qualité nationale vs. valeur centrale"))
        st.plotly_chart(ui.style_fig(fig, 320), width="stretch")
        st.caption(L("يُظهر أي المعاملات غير المعايرة يحدّد النتيجة أكثر: أولوية المعايرة على بيانات حقيقية.", "Montre quels coefficients non calibrés pilotent le résultat : priorités de calibration sur données réelles."))
    with t4:
        st.markdown(L("**التخصيص:** وزن الولاية = (1−λ)·حصة التلاميذ + λ·حصة (التلاميذ × الحاجة)، محصور في النطاق المحدد.", "**Allocation :** poids du gouvernorat = (1−λ)·part des élèves + λ·part (élèves × besoin), restreint au périmètre choisi."))
        st.latex(r"a_g=\frac{(1-\lambda)\,P_g/\sum P+\lambda\,P_g n_g/\sum Pn}{\text{normalisation sur le périmètre}}")
        st.latex(r"\Delta C_g=C_g\frac{x}{1-x},\quad \Delta T^A_g=T_g\frac{x}{1-x},\quad \Delta T^B_g=a_g\,\frac{pct}{100}\sum T,\quad E'_g=1-(1-E_g)e^{-k\,a_gB/(P_g/1000)}")
        st.latex(r"s'=\frac{P}{C+\Delta C},\quad PTR'=\frac{P}{T+\Delta T^A+\Delta T^B}")
        st.latex(r"\Delta Q_g=(1+\gamma n_g)\left[\varepsilon_c\ln\frac{s}{s'}+\varepsilon_p\ln\frac{PTR}{PTR'}+\varepsilon_e(E'-E)\right],\quad D'=D\,e^{-\kappa\,\Delta Q/10}")
        st.latex(r"\text{Coût}=\left(\Delta T\cdot c_t\right)H+\Delta C\cdot c_r+B")
        st.markdown(L("المتغيرات: P التلاميذ، C الأقسام، T المدرّسون، E التجهيز، n الحاجة، x نسبة تخفيض حجم القسم، H أفق الكلفة. التحقق الآلي من المعادلات في tests/test_simulation.py.", "Variables : P élèves, C classes, T enseignants, E équipement, n besoin, x réduction de taille de classe, H horizon. Vérification automatique dans tests/test_simulation.py."))
    with t5:
        c1, c2 = st.columns([3, 1])
        name = c1.text_input(L("اسم السيناريو", "Nom du scénario"), key="sim_name", placeholder=L("مثال: تخفيف الاكتظاظ ١٠٪", "Ex. : classes −10 %"))
        if c2.button(L("حفظ السيناريو", "Enregistrer"), key="sim_save", type="primary", width="stretch", disabled=not ui.can_save_scenario(bundle)):
            if not name.strip():
                st.warning(L("أدخل اسماً.", "Saisissez un nom."))
            else:
                scenario_store.save(name.strip(), asdict(scenario), asdict(asm), {**{k: float(v) for k, v in n.items()}, **{k: float(v) for k, v in c.items()}, "mc_q_p10": q["p10"], "mc_q_p90": q["p90"]}, bundle.provenance.get("institutions", "synthetic"), source_fingerprint=source_fingerprint, random_seed=mc_seed, actor=security.identity(st.session_state)["user_id"], role=security.identity(st.session_state)["role"])
                st.success(L("تم الحفظ.", "Enregistré."))
        if bundle.mode == "REAL_DATA" and not ui.can_save_scenario(bundle):
            st.warning(L("حفظ السيناريوهات على البيانات الحقيقية يتطلب جلسة موثقة بدور محلل أو مدير عبر مزود هوية مؤسسي.", "L’enregistrement de scénarios sur données réelles exige une session authentifiée avec rôle analyste ou administrateur via un fournisseur d’identité institutionnel."))
        hist = scenario_store.list_all()
        if hist.empty:
            st.info(L("لا سيناريوهات محفوظة.", "Aucun scénario enregistré."))
        else:
            show = hist[["id", "created_at", "name", "data", "model_version", "random_seed", "source_fingerprint", "sc_class_size_reduction", "sc_extra_teachers_pct", "sc_equipment_budget_um", "sc_equity_weight", "delta_quality", "delta_dropout_rel", "horizon_total_um"]]
            st.dataframe(show.round(3), hide_index=True, width="stretch")
            if len(hist) >= 2:
                fig = px.scatter(hist, x="horizon_total_um", y="delta_quality", text="name", labels={"horizon_total_um": L("الكلفة الكلية (و.ك)", "Coût total (UC)"), "delta_quality": L("تغيّر الجودة", "Δ qualité")}, color_discrete_sequence=[PALETTE["terracotta"]])
                fig.update_traces(textposition="top center", marker_size=11)
                st.plotly_chart(ui.style_fig(fig, 340), width="stretch")
            st.caption(L("السجل محفوظ محلياً بصلاحيات ملف محدودة. الحذف الإداري غير متاح من واجهة المستخدم في هذا النموذج الأولي.", "Historique conservé localement avec permissions de fichier restreintes. La suppression administrative n'est pas exposée dans cette version prototype."))

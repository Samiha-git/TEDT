import plotly.express as px
import streamlit as st

import ui
from tedt_core import reports, scenario_store
from tedt_core.config import PALETTE
from ui import L


def render():
    bundle = ui.get_bundle()
    gov = bundle.governorates()
    synthetic = ui.is_synthetic(bundle)
    sim = st.session_state.get("last_sim")
    ui.page_title(L("التقارير والرؤى الاستراتيجية", "Rapports et analyses stratégiques"), "file")
    ui.banner(bundle)

    t1, t2, t3 = st.tabs([L("ملخص تنفيذي وتوصيات تحليلية", "Synthèse et constats analytiques"), L("مقارنة السيناريوهات", "Comparaison des scénarios"), L("التصدير", "Exports")])
    lines = reports.insights(gov, ui.lang(), synthetic, sim)
    with t1:
        st.markdown(L("### ملخص تنفيذي (مولَّد آلياً من الجداول الحالية)", "### Synthèse (générée automatiquement à partir des tables courantes)"))
        for s in lines:
            st.markdown(f"- {s}")
        st.caption(L("جمل قاعدية مرتبطة بالأرقام الحالية؛ لا تُعدّ تحليلاً سببياً ولا توصية سياسية.", "Phrases à gabarit liées aux chiffres courants ; ni analyse causale ni recommandation politique."))
        if sim is None:
            st.info(L("شغّل «مختبر محاكاة السياسات» لإضافة نتائج السيناريو إلى التقرير.", "Ouvrez le « Laboratoire de simulation » pour ajouter un scénario au rapport."))
    with t2:
        hist = scenario_store.list_all()
        if len(hist) < 2:
            st.info(L("احفظ سيناريوهين على الأقل في صفحة المختبر للمقارنة.", "Enregistrez au moins deux scénarios dans le laboratoire pour les comparer."))
        else:
            fig = px.bar(hist, x="name", y="delta_quality", color_discrete_sequence=[PALETTE["blue"]], labels={"name": "", "delta_quality": L("تغيّر الجودة", "Δ qualité")})
            st.plotly_chart(ui.style_fig(fig, 340), width="stretch")
            fig = px.bar(hist, x="name", y="horizon_total_um", color_discrete_sequence=[PALETTE["terracotta"]], labels={"name": "", "horizon_total_um": L("الكلفة الكلية (و.ك)", "Coût total (UC)")})
            st.plotly_chart(ui.style_fig(fig, 340), width="stretch")
            st.dataframe(hist.drop(columns=["assumptions"]).round(3), hide_index=True, width="stretch")
    with t3:
        st.download_button(L("مؤشرات الولايات (CSV)", "Indicateurs par gouvernorat (CSV)"), ui.export_frame(gov.drop(columns=["name_fr", "name_ar"]), bundle, ("institutions",)), "tedt_governorates.csv", "text/csv", key="rp_gov")
        hist = scenario_store.list_all()
        if not hist.empty:
            st.download_button(L("سجل السيناريوهات (CSV)", "Historique des scénarios (CSV)"), ui.export_frame(hist, bundle, ("institutions", "results")), "tedt_scenarios.csv", "text/csv", key="rp_hist")
        if reports.pdf_available(ui.lang()):
            try:
                pdf = reports.build_pdf(gov, ui.lang(), synthetic, sim, lines, provenance=bundle.provenance, mode=bundle.mode)
                st.download_button(L("ملخص تنفيذي (PDF)", "Synthèse exécutive (PDF)"), pdf, f"tedt_summary_{ui.lang()}.pdf", "application/pdf", key="rp_pdf")
            except Exception as e:  # noqa: BLE001
                st.error(f"PDF: {e}")
        else:
            st.info(L("تصدير PDF يتطلب reportlab وarabic-reshaper وpython-bidi وخطاً يدعم العربية (انظر README).", "L'export PDF exige reportlab, arabic-reshaper, python-bidi et une police compatible arabe (voir README)."))

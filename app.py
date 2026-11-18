"""TEDT - Tunisia Educational Digital Twin. Entry point:  streamlit run app.py

Presentation layer: institutional header + horizontal navigation + settings bar (see ui.py).
Routing still relies on st.navigation / st.Page (same URLs as before); the sidebar is no longer used.
"""
import streamlit as st

import ui
from views import analytics, assistant, dashboard, early_warning, equity, observatory, reports, simulation_lab

st.set_page_config(page_title="TEDT — Tunisia Education Digital Twin", page_icon="🧭", layout="wide", initial_sidebar_state="collapsed")

st.session_state.setdefault("lang", "fr")
L = ui.L


def _gated(module: str, view):
    return lambda: view.render() if ui.require_module_data(ui.get_bundle(), module) else None


pages = {
    "": st.Page(_gated("dashboard", dashboard), title=L("لوحة القيادة", "Tableau de bord"), icon="📊", default=True),
    "observatory": st.Page(observatory.render, title=L("مرصد البيانات", "Observatoire des données"), icon="🗂️", url_path="observatory"),
    "analytics": st.Page(_gated("analytics", analytics), title=L("تحليلات التعلمات", "Analyse des apprentissages"), icon="📚", url_path="analytics"),
    "early-warning": st.Page(_gated("early_warning", early_warning), title=L("الإنذار المبكر", "Alerte précoce"), icon="🚨", url_path="early-warning"),
    "equity": st.Page(_gated("equity", equity), title=L("الإنصاف الترابي", "Équité territoriale"), icon="🗺️", url_path="equity"),
    "simulation": st.Page(_gated("simulation", simulation_lab), title=L("مختبر المحاكاة", "Laboratoire de simulation"), icon="🧪", url_path="simulation"),
    "assistant": st.Page(_gated("assistant", assistant), title=L("المساعد الذكي", "Assistant"), icon="💬", url_path="assistant"),
    "reports": st.Page(_gated("reports", reports), title=L("التقارير", "Rapports"), icon="📄", url_path="reports"),
}
st.session_state["_tedt_pages"] = pages  # lets views build quick-access links to the registered pages

# Navigation is declared with position="hidden": routing/URLs stay native, the visible bar is ui.nav_bar().
nav = st.navigation(list(pages.values()), position="hidden")

ui.inject_css()
ui.brand_header()
ui.nav_bar(pages)
ui.settings_bar()
nav.run()
ui.footer()

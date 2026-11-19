"""Shared UI helpers: language, RTL styling, banners, maps, data access."""
from __future__ import annotations

from contextlib import contextmanager

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from tedt_core import data_store, security, scenario_store
from tedt_core.config import GOVERNORATES, PALETTE, SEQUENTIAL

DIVERGING_RB = [[0.0, "#F5A623"], [0.5, "#EEF3F8"], [1.0, "#0FA3A3"]]


def lang() -> str:
    return st.session_state.get("lang", "ar")


def L(ar: str, fr: str) -> str:
    return ar if lang() == "ar" else fr


def gname(key: str) -> str:
    fr, ar = GOVERNORATES[key]
    return ar if lang() == "ar" else fr


def name_col() -> str:
    return "name_ar" if lang() == "ar" else "name_fr"


def level_label(level: str) -> str:
    from tedt_core.config import LEVEL_LABELS
    ar, fr = LEVEL_LABELS[level]
    return L(ar, fr)



# ---------------------------------------------------------------------------------------
# Presentation layer: icons, CSS, institutional header, horizontal navigation, panels.
# Everything below is presentation only; no business computation happens here.
# ---------------------------------------------------------------------------------------
_ICONS = {
    "home": '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h5v-6h4v6h5V9.5"/>',
    "chart": '<path d="M5 20V11M11 20V4M17 20v-6M3 21h18"/>',
    "pin": '<path d="M12 21s7-6.2 7-11.5a7 7 0 0 0-14 0C5 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.5"/>',
    "users": '<circle cx="9" cy="8" r="3.2"/><path d="M3 20c0-3.5 2.7-6 6-6s6 2.5 6 6"/><circle cx="17.5" cy="9" r="2.5"/><path d="M17 14.2c2.4.3 4 2.2 4 5"/>',
    "school": '<path d="M3 21h18M5 21V9.5L12 4l7 5.5V21"/><path d="M9.5 21v-5h5v5M9 11.5h.01M15 11.5h.01M12 8.5h.01"/>',
    "trend": '<path d="M3 17l6-6 4 4 8-8"/><path d="M15 7h6v6"/>',
    "alert": '<path d="M12 3.5 2.5 20h19L12 3.5z"/><path d="M12 10v5M12 17.6h.01"/>',
    "scale": '<path d="M12 3v18M7 21h10M4 7h16"/><path d="M4 7 1.5 14a2.8 2.8 0 0 0 5 0L4 7zM20 7l-2.5 7a2.8 2.8 0 0 0 5 0L20 7z"/>',
    "calc": '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M8 7h8M8 12h.01M12 12h.01M16 12h.01M8 16h.01M12 16h.01M16 16h.01"/>',
    "file": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h6"/>',
    "flask": '<path d="M9 3h6M10 3v6l-5.5 10a1.6 1.6 0 0 0 1.4 2.3h12.2a1.6 1.6 0 0 0 1.4-2.3L14 9V3"/><path d="M7.5 15h9"/>',
    "chat": '<path d="M21 12a8 8 0 0 1-11.6 7.1L3 21l1.9-5.4A8 8 0 1 1 21 12z"/>',
    "db": '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>',
    "book": '<path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2z"/><path d="M4 19V5M9 8h6"/>',
    "map": '<path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2z"/><path d="M9 4v14M15 6v14"/>',
    "bolt": '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>',
    "percent": '<path d="M19 5 5 19"/><circle cx="7" cy="7" r="2.5"/><circle cx="17" cy="17" r="2.5"/>',
    "gauge": '<path d="M4 17a8 8 0 1 1 16 0"/><path d="m12 17 4-5"/>',
}

# (url_path, material icon, short FR label, short AR label, inline icon for page headers)
NAV_ITEMS = (
    ("", ":material/home:", "Accueil", "الرئيسية"),
    ("observatory", ":material/database:", "Observatoire", "المرصد"),
    ("analytics", ":material/school:", "Apprentissages", "التعلمات"),
    ("early-warning", ":material/notification_important:", "Alerte précoce", "الإنذار المبكر"),
    ("equity", ":material/map:", "Équité territoriale", "الإنصاف الترابي"),
    ("simulation", ":material/science:", "Simulation", "المحاكاة"),
    ("assistant", ":material/chat:", "Assistant", "المساعد"),
    ("reports", ":material/description:", "Rapports", "التقارير"),
)


def icon(name: str, size: int = 22, stroke: float = 1.9) -> str:
    """Inline SVG icon (stroke style), inheriting the current text colour."""
    body = _ICONS.get(name, _ICONS["chart"])
    return (f'<svg class="tedt-ic" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{body}</svg>')


def inject_css() -> None:
    """Apply the TEDT institutional visual identity (single, central stylesheet), FR/LTR and AR/RTL."""
    rtl = lang() == "ar"
    direction = "rtl" if rtl else "ltr"
    align = "right" if rtl else "left"
    st.markdown(
        f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Poppins:wght@400;500;600;700;800&family=Noto+Sans+Arabic:wght@400;500;600;700;800&display=swap');
:root {{
  --tedt-navy: #0D1B2A;
  --tedt-blue: #1B4F72;
  --tedt-title: #153F63;
  --tedt-teal: #0FA3A3;
  --tedt-green: #20C997;
  --tedt-amber: #F5A623;
  --tedt-bg: #F4F8FC;
  --tedt-panel: #FFFFFF;
  --tedt-soft: #EEF3F8;
  --tedt-sky: #E6F0FA;
  --tedt-border: #DCE6F0;
  --tedt-text: #172B4D;
  --tedt-muted: #64748B;
  --tedt-gutter: 1.5rem;
  --tedt-shadow: 0 3px 14px rgba(13,27,42,.06);
}}
html, body, [class*="css"], .stApp {{
  font-family: {'"Noto Sans Arabic", ' if rtl else ''}'Inter', 'Segoe UI', Tahoma, sans-serif;
  color: var(--tedt-text);
}}
.stApp, [data-testid="stAppViewContainer"] {{ background: var(--tedt-bg); }}
/* The institutional header replaces Streamlit's top bar; the sidebar is no longer used. */
[data-testid="stHeader"] {{ background: transparent; height: 0; min-height: 0; }}
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {{ display: none; }}
[data-testid="stMainBlockContainer"] {{
  padding: 0 var(--tedt-gutter) 1.5rem var(--tedt-gutter); max-width: 100%;
  direction: {direction}; text-align: {align};
}}
[data-testid="stMain"], section.main, .main {{ direction: {direction}; text-align: {align}; }}
[data-testid="stMetric"], [data-testid="stMarkdownContainer"], [data-testid="stCaptionContainer"],
[data-testid="stExpander"], [data-testid="stAlert"], .stRadio, .stSelectbox,
.stMultiSelect, .stSlider, .stTabs, [data-testid="stDataFrame"] {{
  direction: {direction}; text-align: {align};
}}
h1, h2, h3, h4 {{ color: var(--tedt-navy); font-family: 'Poppins', {'"Noto Sans Arabic", ' if rtl else ''}'Inter', sans-serif; letter-spacing: -.02em; }}
h1 {{ font-weight: 800; }}
h2, h3 {{ font-weight: 700; }}
p, label, li {{ color: var(--tedt-text); }}
hr {{ border-color: var(--tedt-border); }}

/* Cards: any bordered Streamlit container */
[data-testid="stVerticalBlockBorderWrapper"] {{
  background: var(--tedt-panel); border: 1px solid var(--tedt-border);
  border-radius: 14px; box-shadow: var(--tedt-shadow);
}}
[data-testid="stMetric"] {{
  background: #FFFFFF; border: 1px solid var(--tedt-border);
  border-inline-start: 4px solid var(--tedt-teal); border-radius: 14px;
  padding: 14px 16px; box-shadow: var(--tedt-shadow);
}}
[data-testid="stMetricLabel"] {{ color: var(--tedt-muted); font-weight: 600; }}
[data-testid="stMetricValue"] {{ direction: ltr; text-align: {align}; color: var(--tedt-navy); font-weight: 800; }}
.stTabs [data-baseweb="tab-list"] {{ gap: 6px; background: #E8EFF6; padding: 5px; border-radius: 12px; }}
.stTabs [data-baseweb="tab"] {{ border-radius: 9px; color: var(--tedt-blue); font-weight: 600; }}
.stTabs [aria-selected="true"] {{ background: #FFFFFF; color: var(--tedt-teal); box-shadow: 0 1px 5px rgba(13,27,42,.08); }}
.stButton > button, .stDownloadButton > button {{
  border-radius: 10px; border: 1px solid var(--tedt-blue); font-weight: 600;
  color: #FFFFFF; background: var(--tedt-blue); transition: .15s ease;
}}
.stButton > button:disabled {{ background: #E8EFF6; border-color: var(--tedt-border); color: #8A9AAF; }}
.stButton > button:hover:not(:disabled), .stDownloadButton > button:hover {{ background: var(--tedt-teal); border-color: var(--tedt-teal); color: #FFFFFF; }}
.stSelectbox [data-baseweb="select"] > div, .stMultiSelect [data-baseweb="select"] > div,
.stTextInput input, .stNumberInput input, .stTextArea textarea {{
  background: #FFFFFF; border-color: var(--tedt-border); border-radius: 10px;
}}
[data-testid="stAlert"] {{ border-radius: 12px; border-width: 1px; }}

/* ---- Institutional header (full width, visible on every page) ---- */
.tedt-brand-header {{
  display: flex; align-items: center; justify-content: space-between; gap: 22px;
  background: linear-gradient(100deg, #FFFFFF 0%, #EAF2FA 55%, #DCE9F5 100%);
  padding: 12px calc(var(--tedt-gutter) + .5rem); margin: 0 calc(-1 * var(--tedt-gutter));
  min-height: 84px; margin-top: -1rem;
}}
.tedt-brand-left {{ display: flex; align-items: center; gap: 18px; min-width: 0; }}
.tedt-logo {{ display: flex; align-items: center; gap: 10px; flex: 0 0 auto; }}
.tedt-logo-img {{ height: 64px; width: auto; max-width: 100%; object-fit: contain; mix-blend-mode: multiply; flex: 0 1 auto; }}
.tedt-wordmark {{ color: var(--tedt-navy); font-family: 'Poppins', sans-serif; font-size: 2.3rem; font-weight: 800; line-height: 1; letter-spacing: -.06em; direction: ltr; }}
.tedt-wordmark span {{ color: var(--tedt-teal); }}
.tedt-brand-sep {{ width: 2px; align-self: stretch; min-height: 44px; background: var(--tedt-blue); opacity: .55; border-radius: 2px; }}
.tedt-brand-name {{ color: var(--tedt-blue); font-family: 'Poppins', 'Inter', sans-serif; font-size: 1.15rem; font-weight: 600; line-height: 1.3; direction: ltr; }}
.tedt-ministry-logo {{ width: min(300px, 32vw); max-height: 74px; object-fit: contain; border-radius: 10px; flex: 0 1 auto; }}

/* ---- Horizontal navigation bar (native st.page_link items) ---- */
.st-key-tedt-navrow {{
  background: #FFFFFF; border-bottom: 1px solid var(--tedt-border);
  margin: 0 calc(-1 * var(--tedt-gutter)) 0.9rem; padding: 0 calc(var(--tedt-gutter) + .25rem);
  width: calc(100% + 2 * var(--tedt-gutter)) !important; max-width: none !important; box-sizing: border-box;
  box-shadow: 0 2px 8px rgba(13,27,42,.04);
}}
.st-key-tedt-nav {{ overflow-x: auto; scrollbar-width: thin; }}
.st-key-tedt-nav [data-testid="stPageLink"] a {{
  border-radius: 0; padding: .8rem .85rem .7rem; color: var(--tedt-text); font-weight: 500; white-space: nowrap;
  border-bottom: 3px solid transparent; background: transparent;
}}
.st-key-tedt-nav [data-testid="stPageLink"] a:hover {{ background: var(--tedt-soft); color: var(--tedt-blue); }}
.st-key-tedt-nav [data-testid="stPageLink"] a[aria-current="page"] {{
  color: var(--tedt-blue); font-weight: 700; border-bottom-color: var(--tedt-teal); background: transparent;
}}
.st-key-tedt-lang {{ display: flex; justify-content: flex-end; }}
.st-key-tedt-lang [role="radiogroup"] {{ gap: 0; background: #EAF0F6; border-radius: 9px; padding: 3px; flex-wrap: nowrap; }}
.st-key-tedt-lang [role="radiogroup"] label {{ padding: 2px 10px; border-radius: 7px; margin: 0; }}
.st-key-tedt-lang [role="radiogroup"] label:has(input:checked) {{ background: var(--tedt-navy); }}
.st-key-tedt-lang [role="radiogroup"] label:has(input:checked) p {{ color: #FFFFFF; font-weight: 700; }}
.st-key-tedt-lang [role="radiogroup"] label > div > div:first-child {{ display: none; }}

/* ---- Settings bar ---- */
.st-key-tedt-settings {{
  background: #FFFFFF; border: 1px solid var(--tedt-border); border-radius: 12px;
  padding: .35rem .9rem; box-shadow: var(--tedt-shadow); margin-bottom: .9rem;
}}
.tedt-set-label {{ color: var(--tedt-title); font-weight: 700; font-size: .92rem; display: flex; align-items: center; gap: 8px; }}
.tedt-set-note {{ color: var(--tedt-muted); font-size: .78rem; line-height: 1.35; }}

/* ---- Page title strip (every module) ---- */
.tedt-page-title {{
  display: flex; align-items: center; gap: 14px; margin: .2rem 0 .9rem;
  background: linear-gradient(100deg, #EAF2FA 0%, #F4F8FC 100%); border: 1px solid var(--tedt-border);
  border-radius: 14px; padding: 14px 18px;
}}
.tedt-page-title .ic {{ width: 44px; height: 44px; border-radius: 50%; background: var(--tedt-title); color: #FFFFFF; display: flex; align-items: center; justify-content: center; flex: 0 0 auto; }}
.tedt-page-title h1 {{ margin: 0; padding: 0; font-size: 1.55rem; line-height: 1.2; }}
.tedt-page-title .sub {{ color: var(--tedt-muted); font-size: .85rem; margin-top: 2px; }}

/* ---- Welcome banner ---- */
.tedt-hero {{
  position: relative; overflow: hidden; border-radius: 14px; border: 1px solid var(--tedt-border);
  background: linear-gradient(100deg, #EDF4FB 0%, #E1EDF8 100%); padding: 26px 34px; margin-bottom: 1rem; min-height: 160px;
  display: flex; align-items: center;
}}
.tedt-hero-text {{ position: relative; z-index: 2; max-width: 58%; }}
.tedt-hero h1 {{ margin: 0; font-size: 2.35rem; font-weight: 800; color: var(--tedt-navy); line-height: 1.15; }}
.tedt-hero .t2 {{ margin: 4px 0 8px; font-family: 'Poppins', sans-serif; font-size: 1.7rem; font-weight: 700; color: var(--tedt-teal); line-height: 1.2; direction: ltr; text-align: {align}; }}
.tedt-hero .t3 {{ font-style: {'normal' if rtl else 'italic'}; font-size: 1.08rem; color: var(--tedt-blue); }}
.tedt-hero-art {{ position: absolute; inset-block: 0; {'left' if rtl else 'right'}: 0; width: 46%; z-index: 1; opacity: .95; pointer-events: none; }}
.tedt-hero-art svg {{ width: 100%; height: 100%; }}

/* ---- KPI cards ---- */
.tedt-kpi-row {{ display: grid; gap: 14px; margin-bottom: 14px; grid-template-columns: repeat(var(--n, 4), minmax(0, 1fr)); }}
.tedt-kpi {{
  display: flex; align-items: center; gap: 14px; background: #FFFFFF; border: 1px solid var(--tedt-border);
  border-inline-start: 5px solid var(--k, var(--tedt-teal)); border-radius: 14px; padding: 14px 16px; box-shadow: var(--tedt-shadow); min-width: 0;
}}
.tedt-kpi .ic {{ width: 52px; height: 52px; border-radius: 50%; background: var(--k, var(--tedt-teal)); color: #FFFFFF; display: flex; align-items: center; justify-content: center; flex: 0 0 auto; }}
.tedt-kpi .tx {{ min-width: 0; }}
.tedt-kpi .v {{ font-family: 'Poppins', 'Inter', sans-serif; font-size: 1.65rem; font-weight: 700; color: var(--tedt-navy); line-height: 1.1; direction: ltr; display: inline-block; }}
.tedt-kpi .l {{ font-size: .86rem; color: var(--tedt-text); font-weight: 500; line-height: 1.3; }}
.tedt-kpi .s {{ font-size: .74rem; color: var(--tedt-muted); line-height: 1.3; }}
.tedt-kpi.tone-blue {{ --k: #1B4F72; }}
.tedt-kpi.tone-teal {{ --k: #0FA3A3; }}
.tedt-kpi.tone-amber {{ --k: #F5A623; }}
.tedt-kpi.tone-navy {{ --k: #0D1B2A; }}
.tedt-kpi.tone-green {{ --k: #20C997; }}
.tedt-kpi .v.long {{ font-size: 1.15rem; }}
.tedt-kpi.no-ic {{ padding: 12px 16px; }}
.tedt-kpi.no-ic .v {{ font-size: 1.5rem; }}
.tedt-badge {{ display: inline-block; padding: 3px 10px; border-radius: 20px; font-size: .78rem; font-weight: 700; }}
.tedt-badge.syn {{ background: #FFF2D9; color: #8A5A00; }}
.tedt-badge.usr {{ background: #DDF7EF; color: #087A62; }}
.tedt-tag {{ font-size: .8rem; letter-spacing: .02em; color: var(--tedt-teal); font-weight: 700; }}

/* ---- Panels with institutional title bar ---- */
.st-key-tedt-panel-map, .st-key-tedt-panel-rank, .st-key-tedt-panel-more {{ padding-top: 0; overflow: hidden; }}
.tedt-panel-title {{
  display: flex; align-items: center; gap: 10px; background: var(--tedt-title); color: #FFFFFF;
  font-family: 'Poppins', 'Inter', sans-serif; font-weight: 600; font-size: 1.02rem;
  margin: 0 -1rem .8rem; padding: 11px 16px;
}}

/* ---- Quick access cards (native st.page_link) ---- */
.tedt-quick-title {{ display: flex; align-items: center; gap: 8px; color: var(--tedt-title); font-weight: 700; margin: .4rem 0 .5rem; }}
[class*="st-key-tedt-quick-"] [data-testid="stPageLink"] {{ width: 100%; }}
[class*="st-key-tedt-quick-"] [data-testid="stPageLink"] a {{
  background: #FFFFFF; border: 1px solid var(--tedt-border); border-radius: 12px; padding: .85rem 1rem;
  box-shadow: var(--tedt-shadow); width: 100%; font-weight: 600; color: var(--tedt-navy); justify-content: flex-start;
}}
[class*="st-key-tedt-quick-"] [data-testid="stPageLink"] a:hover {{ border-color: var(--tedt-teal); background: #F7FCFC; }}
[class*="st-key-tedt-quick-"] [data-testid="stPageLink"] a span[data-testid="stIconMaterial"] {{
  color: #FFFFFF; background: var(--q, var(--tedt-blue)); border-radius: 50%; width: 38px; height: 38px;
  display: inline-flex; align-items: center; justify-content: center; font-size: 22px; margin-inline-end: .35rem;
}}
[class*="st-key-tedt-quick-"] [data-testid="stPageLink"] a::after {{ content: "{'‹' if rtl else '›'}"; margin-inline-start: auto; font-size: 1.6rem; color: var(--tedt-muted); }}
.st-key-tedt-quick-1 {{ --q: #1B4F72; }} .st-key-tedt-quick-2 {{ --q: #0FA3A3; }}
.st-key-tedt-quick-3 {{ --q: #F5A623; }} .st-key-tedt-quick-4 {{ --q: #0D1B2A; }}
.tedt-footer {{ text-align: center; color: var(--tedt-muted); font-size: .78rem; padding: 1.2rem 0 .4rem; }}
.tedt-footer b {{ color: var(--tedt-navy); }}

@media (max-width: 1100px) {{
  .tedt-kpi-row {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
  .tedt-hero-text {{ max-width: 70%; }}
}}
@media (max-width: 800px) {{
  :root {{ --tedt-gutter: .75rem; }}
  .tedt-brand-header {{ padding: 8px .9rem; gap: 10px; min-height: 64px; }}
  .tedt-logo-img {{ height: 38px; }}
  .tedt-wordmark {{ font-size: 1.5rem; }}
  .tedt-brand-sep, .tedt-brand-name {{ display: none; }}
  .tedt-ministry-logo {{ width: 44vw; max-height: 52px; }}
  .tedt-kpi-row {{ grid-template-columns: 1fr; }}
  .tedt-hero {{ padding: 18px; }}
  .tedt-hero-text {{ max-width: 100%; }}
  .tedt-hero h1 {{ font-size: 1.6rem; }}
  .tedt-hero .t2 {{ font-size: 1.2rem; }}
  .tedt-hero-art {{ opacity: .25; width: 70%; }}
}}
</style>
""",
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner=False)
def _image_uri(filename: str, mime: str) -> str:
    """Base64 data URI of an image from assets/branding (empty string if the file is missing)."""
    import base64
    path = __import__("pathlib").Path(__file__).resolve().parent / "assets" / "branding" / filename
    if not path.exists():
        return ""
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def brand_header() -> None:
    """Institutional header: official TEDT logo (assets/branding/Logo_TEDT.jpeg) on one side,
    the language-matched Ministry logo on the other."""
    rtl = lang() == "ar"
    ministry_uri = _image_uri("ministry_logo_ar.png" if rtl else "ministry_logo_fr.png", "image/png")
    alt = "وزارة التربية" if rtl else "Ministère de l’Éducation"
    ministry = f'<img class="tedt-ministry-logo" src="{ministry_uri}" alt="{alt}" />' if ministry_uri else ""
    tedt_uri = _image_uri("Logo_TEDT.jpeg", "image/jpeg")
    if tedt_uri:
        tedt_logo = f'<img class="tedt-logo-img" src="{tedt_uri}" alt="TEDT — Tunisia Education Digital Twin" />'
    else:  # fallback if the logo file is absent
        tedt_logo = '<div class="tedt-wordmark">TED<span>T</span></div><div class="tedt-brand-sep"></div><div class="tedt-brand-name">Tunisia Education Digital Twin</div>'
    st.markdown(
        f"""
<div class="tedt-brand-header" dir="{'rtl' if rtl else 'ltr'}">
  <div class="tedt-brand-left">{tedt_logo}</div>
  {ministry}
</div>
""",
        unsafe_allow_html=True,
    )


def nav_bar(pages: dict[str, "st.Page"]) -> None:
    """Horizontal primary navigation (real st.page_link items) + FR/AR switch, right under the header."""
    with st.container(key="tedt-navrow"):
        c_nav, c_lang = st.columns([8.2, 1.3], vertical_alignment="center")
        with c_nav:
            with st.container(horizontal=True, wrap=False, gap="xsmall", key="tedt-nav"):
                for path, mat_icon, fr, ar in NAV_ITEMS:
                    st.page_link(pages[path], label=L(ar, fr), icon=mat_icon)
        with c_lang:
            with st.container(key="tedt-lang"):
                st.radio("اللغة / Langue", ["fr", "ar"], key="lang", horizontal=True, label_visibility="collapsed",
                         format_func=lambda v: "FR" if v == "fr" else "عربي")


def settings_bar() -> None:
    """Compact settings zone (data mode + provenance reminder) replacing the former sidebar controls."""
    with st.container(key="tedt-settings"):
        c1, c2, c3 = st.columns([1.5, 2.6, 5], vertical_alignment="center")
        c1.markdown(f'<div class="tedt-set-label">{icon("db", 18)} {L("وضع العرض", "Mode d’affichage")}</div>', unsafe_allow_html=True)
        with c2:
            mode_selector()
        c3.markdown(f'<div class="tedt-set-note">{L("وضع البيانات محدد هنا؛ الملفات المستوردة لا تُعدّ مصادر رسمية معتمدة تلقائياً.", "Le mode de données se règle ici ; un fichier importé n’est pas automatiquement une source officielle certifiée.")}</div>', unsafe_allow_html=True)


def page_title(title: str, icon_name: str = "chart", subtitle: str = "") -> None:
    sub = f'<div class="sub">{subtitle}</div>' if subtitle else ""
    st.markdown(f'<div class="tedt-page-title"><span class="ic">{icon(icon_name, 24)}</span><div><h1>{title}</h1>{sub}</div></div>', unsafe_allow_html=True)


_HERO_ART = """<svg viewBox="0 0 560 200" preserveAspectRatio="xMaxYMid meet" aria-hidden="true">
<defs><linearGradient id="hf" x1="0" x2="1"><stop offset="0" stop-color="#E1EDF8" stop-opacity="0"/><stop offset=".35" stop-color="#E1EDF8" stop-opacity=".9"/><stop offset="1" stop-color="#E1EDF8" stop-opacity="0"/></linearGradient></defs>
<g fill="#FFFFFF" stroke="#B9CCE0" stroke-width="1.5">
<rect x="150" y="46" width="330" height="112" rx="3"/><rect x="150" y="38" width="330" height="10" fill="#D5E4F2"/>
</g>
<g fill="#C9DBEC" stroke="#B2C7DC" stroke-width="1">
""" + "".join(f'<rect x="{170 + c * 50}" y="{62 + r * 32}" width="30" height="20" rx="2"/>' for r in range(3) for c in range(6)) + """
</g>
<rect x="296" y="120" width="34" height="38" fill="#B9CCE0"/>
<g fill="#9FD2C9" opacity=".9"><circle cx="110" cy="120" r="30"/><circle cx="508" cy="106" r="38"/><circle cx="534" cy="132" r="26"/></g>
<g fill="#7C8FA3"><rect x="107" y="140" width="6" height="22"/><rect x="505" y="130" width="7" height="32"/></g>
<path d="M0 162 H560" stroke="#B9CCE0" stroke-width="2"/>
<g stroke="#0FA3A3" stroke-width="5" stroke-linecap="round" opacity=".35"><path d="M120 28 L150 4"/><path d="M136 34 L172 6"/></g>
</svg>"""


def hero() -> None:
    st.markdown(
        f"""
<div class="tedt-hero">
  <div class="tedt-hero-text">
    <h1>{L("مرحباً بكم في TEDT", "Bienvenue sur TEDT")}</h1>
    <div class="t2">Tunisia Education Digital Twin</div>
    <div class="t3">{L("بيانات موثوقة من أجل تعليم أكثر إنصافاً واستدامة", "Des données fiables pour une éducation plus équitable et durable")}</div>
  </div>
  <div class="tedt-hero-art">{_HERO_ART}</div>
</div>
""",
        unsafe_allow_html=True,
    )





@contextmanager
def panel(title: str, icon_name: str = "chart", key: str = "tedt-panel-more"):
    """White card with a dark institutional title bar; widgets/charts go inside the ``with`` block."""
    with st.container(border=True, key=key):
        st.markdown(f'<div class="tedt-panel-title">{icon(icon_name, 20)}<span>{title}</span></div>', unsafe_allow_html=True)
        yield


def quick_access(items: list[tuple["st.Page", str, str]]) -> None:
    """Quick access cards: (page, label, material icon). Real page links, keeping session state."""
    st.markdown(f'<div class="tedt-quick-title">{icon("bolt", 18)} {L("وصول سريع", "Accès rapide")}</div>', unsafe_allow_html=True)
    cols = st.columns(len(items))
    for i, (col, (page, label, mat_icon)) in enumerate(zip(cols, items), start=1):
        with col, st.container(key=f"tedt-quick-{i}"):
            st.page_link(page, label=label, icon=mat_icon, width="stretch")


def footer() -> None:
    st.markdown(
        '<div class="tedt-footer"><b>TEDT</b> — Tunisia Education Digital Twin · Understand. Anticipate. Simulate. Transform.</div>',
        unsafe_allow_html=True,
    )




def get_bundle() -> data_store.DataBundle:
    mode = st.session_state.get("data_mode", "DEMONSTRATION")
    return data_store.build_bundle(st.session_state.get("overrides"), mode=mode,
                                   validation=st.session_state.get("override_report", {}))


MODULE_REQUIREMENTS = {
    "dashboard": ("institutions", "results"),
    "analytics": ("results", "exam_items", "curriculum"),
    "early_warning": ("students",),
    "equity": ("institutions",),
    "simulation": ("institutions",),
    "assistant": ("institutions", "results"),
    "reports": ("institutions", "results"),
}

def require_module_data(bundle: data_store.DataBundle, module: str) -> bool:
    required = MODULE_REQUIREMENTS.get(module, ())
    missing = [name for name in required if bundle.provenance.get(name) == "unavailable" or getattr(bundle, name, pd.DataFrame()).empty]
    if module in {"dashboard", "equity", "simulation", "reports"} and not missing:
        coverage = data_store.governorate_coverage(bundle.institutions)
        if not coverage["complete"]:
            missing.append(f"couverture territoriale {coverage['observed']}/{coverage['expected']}")
    if module == "simulation" and not missing:
        try:
            sim_gov = bundle.governorates()
            needed = ("equipment_index", "quality", "dropout", "deprivation_index")
            if any(c not in sim_gov or sim_gov[c].isna().any() for c in needed):
                missing.append("indicateurs complets requis pour la simulation")
        except Exception:
            missing.append("agrégats valides pour la simulation")
    if module == "reports" and not missing:
        try:
            report_gov = bundle.governorates()
            for col in ("quality", "dropout"):
                if col not in report_gov or report_gov[col].isna().any():
                    missing.append(f"{col} (incomplet)")
        except Exception:
            missing.append("indicateurs agrégés valides")
    if missing:
        labels = {"institutions": "établissements", "results": "résultats", "exam_items": "items d'examen", "curriculum": "programmes", "students": "dossiers élèves agrégés", "context": "contexte territorial"}
        st.warning(L("لا يمكن تشغيل هذا القسم: البيانات المطلوبة غير متاحة في وضع البيانات الحقيقية.",
                     "Module bloqué : les jeux de données requis ne sont pas disponibles en mode données réelles.") + " " + ", ".join(labels.get(x, x) for x in missing))
        st.caption(L("لم يتم استبدال البيانات الناقصة ببيانات اصطناعية.", "Aucune donnée synthétique n'a été substituée aux données manquantes."))
        return False
    return True

def export_frame(df: pd.DataFrame, bundle: data_store.DataBundle, datasets: tuple[str, ...]) -> bytes:
    return data_store.export_frame(df, bundle.mode, bundle.provenance, datasets)


def is_synthetic(bundle: data_store.DataBundle, dataset: str = "institutions") -> bool:
    return bundle.provenance.get(dataset, "synthetic") == "synthetic"


def banner(bundle: data_store.DataBundle) -> None:
    if bundle.mode == "DEMONSTRATION":
        st.warning(L(
            "⚠️ **وضع العرض التوضيحي — بيانات اصطناعية بالكامل**. لا تمثل هذه القيم الواقع الفعلي لأي ولاية أو مؤسسة، ولا يجوز استخدامها كإحصاءات رسمية أو لتقييم أثر السياسات.",
            "⚠️ **MODE DÉMONSTRATION — DONNÉES ENTIÈREMENT SYNTHÉTIQUES**. Ces valeurs ne décrivent aucun gouvernorat ni établissement réel et ne doivent pas être utilisées comme statistiques officielles ou évaluations d'impact."))
    else:
        status = ", ".join(f"{k}={v}" for k, v in bundle.provenance.items())
        st.info(L("وضع البيانات الحقيقية: لا تُعرض إلا مجموعات البيانات المستوردة والمتحقق من بنيتها؛ ويظل مصدرها الرسمي بحاجة إلى اعتماد. " + status,
                  "MODE DONNÉES RÉELLES : seuls les jeux importés et structurellement validés sont exposés ; leur origine officielle reste à certifier. " + status))
        st.caption(L("كل مؤشر يعتمد فقط على المصادر المبينة؛ أي مصدر غير متاح يمنع الحساب ولا يُستبدل اصطناعياً.",
                     "Chaque indicateur dépend exclusivement des sources indiquées ; une source indisponible bloque le calcul et n'est jamais remplacée par une donnée synthétique."))

def _mode_changed() -> None:
    # Prevent cross-mode residue in scenario/assistant state.
    for key in ("last_sim", "chat", "priority_top"):
        st.session_state.pop(key, None)
    ident = security.identity(st.session_state)
    scenario_store.log_event("mode_changed", ident["user_id"], {"mode": st.session_state.get("data_mode", "DEMONSTRATION")})

def can_import_dataset() -> bool:
    return security.allowed(st.session_state, "import_aggregate")

def can_save_scenario(bundle: data_store.DataBundle) -> bool:
    if bundle.mode == "DEMONSTRATION":
        return True  # local synthetic scenarios contain no real pupil/teacher records
    return security.allowed(st.session_state, "save_scenario")

def _mode_widget_changed(widget_key: str) -> None:
    st.session_state["data_mode"] = st.session_state[widget_key]
    _mode_changed()


def mode_selector() -> None:
    """Data-mode selector. ``data_mode`` stays the single source of truth (same key and same
    side-effects as before); the widget key is per-language so labels refresh when the language changes."""
    wkey = f"data_mode_ui_{lang()}"
    st.session_state[wkey] = st.session_state.get("data_mode", "DEMONSTRATION")
    st.selectbox(L("وضع البيانات", "Mode de données"), ["DEMONSTRATION", "REAL_DATA"], key=wkey,
                 on_change=_mode_widget_changed, args=(wkey,), label_visibility="collapsed",
                 format_func=lambda x: L("عرض توضيحي — اصطناعي", "Démonstration — synthétique") if x == "DEMONSTRATION" else L("بيانات حقيقية — مستوردة فقط", "Données réelles — imports uniquement"))


_TONES = ("blue", "teal", "amber", "navy", "green")


def card(label: str, value: str, sub: str = "", icon_name: str | None = None, tone: str = "teal") -> str:
    ic = f'<span class="ic">{icon(icon_name, 26)}</span>' if icon_name else ""
    vcls = " long" if len(str(value)) > 9 else ""
    cls = "tedt-kpi tone-" + tone + ("" if icon_name else " no-ic")
    return (f'<div class="{cls}">{ic}<div class="tx"><span class="v{vcls}">{value}</span>'
            f'<div class="l">{label}</div><div class="s">{sub}</div></div></div>')


def cards(items: list[tuple[str, str, str]], icons: list[str] | None = None, tones: list[str] | None = None) -> None:
    """Horizontal KPI cards. Values are passed in by the caller (computed by the TEDT engine)."""
    html = []
    for i, (label, value, sub) in enumerate(items):
        tone = (tones or _TONES)[i % len(tones or _TONES)] if (tones or icons) else "teal"
        html.append(card(label, value, sub, icons[i] if icons else None, tone))
    st.markdown(f'<div class="tedt-kpi-row" style="--n:{len(items)}">{"".join(html)}</div>', unsafe_allow_html=True)


def fmt_int(x: float) -> str:
    return f"{x:,.0f}".replace(",", " ")


def provenance_fig(fig: go.Figure) -> go.Figure:
    mode = st.session_state.get("data_mode", "DEMONSTRATION")
    text = "SYNTHETIC DEMONSTRATION · NOT OFFICIAL DATA" if mode == "DEMONSTRATION" else "IMPORTED DATA · SOURCE NOT CERTIFIED"
    fig.add_annotation(text=text, xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
                       opacity=0.18, textangle=-18, font=dict(size=17, color="#7B8794"),
                       xanchor="center", yanchor="middle")
    return fig


def style_fig(fig: go.Figure, height: int = 420) -> go.Figure:
    provenance_fig(fig)
    fig.update_layout(
        height=height, margin=dict(l=10, r=10, t=50, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(255,255,255,0.6)",
        font=dict(family="Inter, Noto Sans Arabic, Segoe UI, Tahoma, sans-serif", color=PALETTE["ink"]),
        legend=dict(orientation="h", y=-0.15),
    )
    return fig


def choropleth(gov: pd.DataFrame, col: str, title: str, *, diverging: bool = False, reverse: bool = False, hover: dict[str, str] | None = None, zmid: float | None = None, height: int = 520) -> go.Figure:
    """Build a governorate map while accepting the supported name schemas.

    The national bundle uses name_fr/name_ar, while the Lot 1 synthetic
    demonstration file uses governorate_fr/governorate_ar. The geographic
    join key remains the stable ``governorate`` code in both cases.
    """
    required = {"governorate", col}
    missing = required.difference(gov.columns)
    if missing:
        raise ValueError(
            "Colonnes obligatoires absentes pour la carte : "
            + ", ".join(sorted(missing))
            + f". Colonnes disponibles : {list(gov.columns)}"
        )

    preferred = name_col()
    localized_fallback = "governorate_ar" if lang() == "ar" else "governorate_fr"
    candidates = (preferred, localized_fallback, "name_ar", "name_fr",
                  "governorate_ar", "governorate_fr", "governorate")
    nm = next((candidate for candidate in candidates if candidate in gov.columns), None)
    if nm is None:
        raise ValueError(
            "Aucune colonne de libellé géographique reconnue. "
            f"Colonnes disponibles : {list(gov.columns)}"
        )

    hover_items = [(key, label) for key, label in (hover or {}).items()
                   if key in gov.columns]
    custom = [gov[nm]] + [gov[key] for key, _label in hover_items]
    hover_text = (
        "<b>%{customdata[0]}</b><br>" + title + ": %{z:.2f}<br>"
        + "".join(
            f"{label}: %{{customdata[{index + 1}]:.2f}}<br>"
            for index, (_key, label) in enumerate(hover_items)
        )
        + "<extra></extra>"
    )

    colorscale = DIVERGING_RB if diverging else SEQUENTIAL
    fig = go.Figure(
        go.Choroplethmap(
            geojson=data_store.geojson(),
            locations=gov["governorate"],
            z=gov[col],
            featureidkey="properties.shapeName",
            colorscale=colorscale,
            reversescale=reverse,
            zmid=zmid,
            marker_line_width=0.8,
            marker_line_color="white",
            customdata=pd.concat(custom, axis=1).to_numpy(),
            hovertemplate=hover_text,
            colorbar=dict(title=dict(text=title, side="right"), thickness=12),
        )
    )
    fig.update_layout(
        map=dict(style="white-bg", center=dict(lat=33.9, lon=9.6), zoom=5.1),
        height=height,
        margin=dict(l=0, r=0, t=10, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
    )
    provenance_fig(fig)
    return fig


def provenance_badge(kind: str) -> str:
    if kind == "synthetic":
        return f'<span class="tedt-badge syn">{L("اصطناعي", "Synthétique")}</span>'
    return f'<span class="tedt-badge usr">{L("مستورد", "Importé")}</span>'

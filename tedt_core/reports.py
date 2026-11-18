"""Report generation: rule-based insights, CSV and PDF (Arabic shaping via arabic-reshaper + python-bidi)."""
from __future__ import annotations

import io
from datetime import date
from pathlib import Path

import pandas as pd

from .config import GOVERNORATES
from .metrics import top_bottom_gap, weighted_gini, weighted_mean

_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
]
_FONT_BOLD_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


def _first(paths):
    return next((p for p in paths if Path(p).exists()), None)


def pdf_available(lang: str = "ar") -> bool:
    try:
        import reportlab  # noqa: F401
    except ImportError:
        return False
    if lang == "ar":
        try:
            import arabic_reshaper  # noqa: F401
            import bidi  # noqa: F401
        except ImportError:
            return False
    return _first(_FONT_CANDIDATES) is not None


def _gn(k: str, lang: str) -> str:
    fr, ar = GOVERNORATES.get(k, (str(k), str(k)))
    return ar if lang == "ar" else fr


def insights(gov: pd.DataFrame, lang: str, synthetic: bool, sim: dict | None = None) -> list[str]:
    """Analytical statements computed from the data; each carries the data-status caveat once."""
    P = gov["pupils"].to_numpy(float)
    out = []
    worst_ptr = gov.sort_values("ptr", ascending=False).head(3)
    low_q = gov.sort_values("quality").head(3)
    hi_drop = gov.sort_values("dropout", ascending=False).head(3)
    names = lambda d: "، ".join(_gn(k, lang) for k in d["governorate"]) if lang == "ar" else ", ".join(_gn(k, lang) for k in d["governorate"])  # noqa: E731
    if lang == "ar":
        out.append(f"أعلى ثلاث ولايات في عدد التلاميذ لكل مدرّس: {names(worst_ptr)}.")
        out.append(f"أدنى ثلاث ولايات في مؤشر جودة التعلمات: {names(low_q)}.")
        out.append(f"أعلى ثلاث ولايات في نسبة الانقطاع: {names(hi_drop)}.")
        out.append(f"الفجوة بين الربع الأعلى والأدنى (مرجّحة بالتلاميذ) في مؤشر الجودة: {top_bottom_gap(gov['quality'], P):.1f} نقطة؛ معامل جيني: {weighted_gini(gov['quality'], P):.3f}.")
        c = weighted_mean(gov["class_size"], P)
        out.append(f"متوسط حجم القسم مرجّحاً بالتلاميذ: {c:.1f}.")
        if sim:
            n = sim["national"]
            out.append(f"السيناريو الأخير: تغيّر الجودة {n['delta_quality']:+.2f} نقطة، وتغيّر الانقطاع النسبي {n['delta_dropout_rel'] * 100:+.1f}% (محاكاة بمعاملات غير معايرة).")
        if synthetic:
            out.append("تنبيه: جميع هذه الاستنتاجات محسوبة على بيانات اصطناعية، وهي توضّح طريقة التحليل لا واقع الولايات.")
    else:
        out.append(f"Trois gouvernorats avec le plus d'élèves par enseignant : {names(worst_ptr)}.")
        out.append(f"Trois gouvernorats avec l'indice de qualité le plus bas : {names(low_q)}.")
        out.append(f"Trois gouvernorats avec le taux d'abandon le plus élevé : {names(hi_drop)}.")
        out.append(f"Écart entre quartiles haut et bas (pondéré par les élèves) sur l'indice de qualité : {top_bottom_gap(gov['quality'], P):.1f} points ; Gini : {weighted_gini(gov['quality'], P):.3f}.")
        out.append(f"Taille moyenne de classe pondérée par les élèves : {weighted_mean(gov['class_size'], P):.1f}.")
        if sim:
            n = sim["national"]
            out.append(f"Dernier scénario : variation de qualité {n['delta_quality']:+.2f} points, variation relative de l'abandon {n['delta_dropout_rel'] * 100:+.1f} % (simulation à paramètres non calibrés).")
        if synthetic:
            out.append("Attention : toutes ces conclusions sont calculées sur des données synthétiques ; elles illustrent la méthode, pas la réalité des gouvernorats.")
    return out


def build_pdf(gov: pd.DataFrame, lang: str, synthetic: bool, sim: dict | None, insight_lines: list[str], provenance: dict | None = None, mode: str = "DEMONSTRATION") -> bytes:
    if lang == "ar":
        try:
            import arabic_reshaper
            from bidi.algorithm import get_display
        except ImportError as exc:
            raise RuntimeError("Arabic PDF requires arabic-reshaper and python-bidi (install requirements.txt).") from exc
    else:
        get_display = None
        arabic_reshaper = None
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    regular, bold = _first(_FONT_CANDIDATES), _first(_FONT_BOLD_CANDIDATES) or _first(_FONT_CANDIDATES)
    if "TEDT-R" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("TEDT-R", regular))
        pdfmetrics.registerFont(TTFont("TEDT-B", bold))
    rtl = lang == "ar"
    required = ("pupils", "teachers", "classes", "quality", "dropout")
    if any(c not in gov or gov[c].isna().any() for c in required):
        raise ValueError("PDF export blocked: required indicators contain missing values.")

    def tx(s: str) -> str:
        s = str(s)
        if rtl:
            s = get_display(arabic_reshaper.reshape(s))
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    align = TA_RIGHT if rtl else TA_LEFT
    base = ParagraphStyle("b", fontName="TEDT-R", fontSize=9.5, leading=14, alignment=align)
    h1 = ParagraphStyle("h1", parent=base, fontName="TEDT-B", fontSize=16, leading=22, textColor=colors.HexColor("#0B3E57"))
    h2 = ParagraphStyle("h2", parent=base, fontName="TEDT-B", fontSize=12, leading=16, textColor=colors.HexColor("#0B5C7A"), spaceBefore=8)
    warn = ParagraphStyle("w", parent=base, backColor=colors.HexColor("#FBEAD0"), borderPadding=6, textColor=colors.HexColor("#6B4400"))
    cell = ParagraphStyle("c", parent=base, fontSize=8, leading=10)

    def P(text, style=base):
        return Paragraph(tx(text), style)

    def table(rows, widths):
        data = [[Paragraph(tx(c), cell) for c in (reversed(r) if rtl else r)] for r in rows]
        if rtl:
            widths = list(reversed(widths))
        t = Table(data, colWidths=widths, repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E3EEF3")), ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#B8C4CC")),
                               ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
        return t

    T = (lambda ar, fr: ar if rtl else fr)
    P_ = gov["pupils"].to_numpy(float)
    story = [P(T("منصة TEDT — ملخص تنفيذي", "TEDT — Synthèse exécutive"), h1),
             P(f"Tunisia Educational Digital Twin · {date.today().isoformat()}"),
             P(T(f"وضع البيانات: {mode} · المصادر: {provenance or {}}", f"Mode de données : {mode} · Sources : {provenance or {}}")), Spacer(1, 6)]
    if synthetic:
        story += [P(T("بيانات تجريبية اصطناعية: الأرقام ليست إحصائيات رسمية ولا تصف واقع أي ولاية أو مؤسسة.",
                      "Données de démonstration synthétiques : ces chiffres ne sont pas des statistiques officielles et ne décrivent aucun gouvernorat ni établissement réel."), warn), Spacer(1, 6)]
    else:
        story += [P(T("بيانات مستوردة: تم التحقق من البنية فقط؛ لم يتم اعتماد المصدر المؤسسي رسمياً.",
                      "Données importées : contrôle structurel effectué uniquement ; la source institutionnelle n'est pas encore certifiée."), warn), Spacer(1, 6)]
    story.append(P(T("المؤشرات الوطنية", "Indicateurs nationaux"), h2))
    kp = [[T("المؤشر", "Indicateur"), T("القيمة", "Valeur")],
          [T("المؤسسات", "Établissements"), f"{int(gov['institutions'].sum()):,}"],
          [T("التلاميذ", "Élèves"), f"{int(gov['pupils'].sum()):,}"],
          [T("المدرسون", "Enseignants"), f"{int(gov['teachers'].sum()):,}"],
          [T("حجم القسم", "Taille de classe"), f"{gov['pupils'].sum() / gov['classes'].sum():.1f}"],
          [T("جودة التعلمات (0-100)", "Qualité des apprentissages (0-100)"), f"{weighted_mean(gov['quality'], P_):.1f}"],
          [T("نسبة الانقطاع", "Taux d'abandon"), f"{weighted_mean(gov['dropout'], P_) * 100:.1f}%"]]
    story += [table(kp, [8 * cm, 5 * cm]), P(T("استنتاجات تحليلية", "Constats analytiques"), h2)]
    story += [P("• " + s) for s in insight_lines]
    if sim:
        n, c, s = sim["national"], sim["costs"], sim["scenario"]
        story.append(P(T("آخر سيناريو محاكاة", "Dernier scénario simulé"), h2))
        story.append(P(T(f"تخفيض حجم القسم {s['class_size_reduction'] * 100:.0f}% · مدرّسون إضافيون {s['extra_teachers_pct']:.1f}% · تجهيز {s['equipment_budget_um']:,.0f} و.ك · وزن الإنصاف {s['equity_weight']:.0%}",
                         f"Réduction de la taille de classe {s['class_size_reduction'] * 100:.0f} % · enseignants supplémentaires {s['extra_teachers_pct']:.1f} % · équipement {s['equipment_budget_um']:,.0f} UC · poids d'équité {s['equity_weight']:.0%}")))
        sr = [[T("المؤشر", "Indicateur"), T("قبل", "Avant"), T("بعد", "Après")],
              [T("جودة التعلمات", "Qualité"), f"{n['quality_before']:.2f}", f"{n['quality_after']:.2f}"],
              [T("الانقطاع %", "Abandon %"), f"{n['dropout_before'] * 100:.2f}", f"{n['dropout_after'] * 100:.2f}"],
              [T("فجوة الأرباع", "Écart quartiles"), f"{n['gap_before']:.2f}", f"{n['gap_after']:.2f}"],
              [T("تلميذ/مدرّس", "Élèves/enseignant"), f"{n['ptr_before']:.2f}", f"{n['ptr_after']:.2f}"],
              [T(f"الكلفة على {c['horizon_years']} سنوات (و.ك)", f"Coût sur {c['horizon_years']} ans (UC)"), "", f"{c['horizon_total_um']:,.0f}"]]
        story += [table(sr, [7 * cm, 3.5 * cm, 3.5 * cm]), Spacer(1, 4),
                  P(T("محاكاة حسابية مبسّطة بمعاملات تأثير غير معايرة على بيانات حقيقية؛ وحدة الكلفة (و.ك) = كلفة مدرّس لسنة. ليست تقديراً إحصائياً.",
                      "Simulation arithmétique simplifiée à paramètres d'effet non calibrés sur des données réelles ; unité de coût (UC) = coût d'un enseignant-année. Ce n'est pas une estimation statistique."), warn)]
    story.append(P(T("الولايات", "Gouvernorats"), h2))
    rows = [[T("الولاية", "Gouvernorat"), T("التلاميذ", "Élèves"), T("حجم القسم", "Classe"), T("تلميذ/مدرّس", "Él./ens."), T("الجودة", "Qualité"), T("الانقطاع %", "Abandon %")]]
    for _, r in gov.sort_values("name_ar" if rtl else "name_fr").iterrows():
        rows.append([_gn(r["governorate"], lang), f"{int(r['pupils']):,}", f"{r['class_size']:.1f}", f"{r['ptr']:.1f}", f"{r['quality']:.1f}", f"{float(r['dropout']) * 100:.1f}"])
    story.append(table(rows, [3.6 * cm, 2.6 * cm, 2.4 * cm, 2.6 * cm, 2.4 * cm, 2.6 * cm]))
    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm, bottomMargin=1.8 * cm, title="TEDT").build(story)
    return buf.getvalue()

"""AI Policy Assistant - DEMO backend (no language model is connected).

The assistant answers a fixed set of intents with rules over the platform's own tables and over the
source catalog, and always attaches sources and the data status. It never invents references.
`AssistantBackend` is the integration point: a real LLM/RAG service must implement `answer` and
keep the same contract (answer text + list of sources with a verification status).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .config import GOVERNORATES


@dataclass
class Answer:
    text: str
    sources: list[tuple[str, str, str]] = field(default_factory=list)  # (title, url, status label)
    mode: str = "demo-rules"


class AssistantBackend:
    name = "abstract"

    def answer(self, question: str, lang: str, ctx: dict) -> Answer:  # pragma: no cover - interface
        raise NotImplementedError


STATUS_FR = {1: "disponible et sourcé", 2: "partiel", 3: "à confirmer (probable en interne)", 4: "non vérifié"}
STATUS_AR = {1: "متوفر ومثبت", 2: "جزئي", 3: "يلزم تأكيد (يُرجَّح داخلياً)", 4: "غير متوفر/لم يُتحقق منه"}

_KW = {
    "disparity": ["تفاوت", "فوارق", "الفوارق", "تباين", "disparit", "inégal", "inegal", "écart", "inequal", "disparity"],
    "scenario": ["أثر", "تخفيف", "اكتظاظ", "سيناريو", "scénario", "scenario", "surcharge", "impact", "effet", "effect"],
    "indicators": ["يراقب", "مؤشرات", "indicateur", "suivre", "monitor", "surveill"],
    "sources": ["مصادر", "غير متوفر", "متوفرة", "source", "données manquantes", "missing", "indisponible", "disponibles"],
}


def _intent(q: str) -> str:
    low = q.lower()
    # order matters: 'sources' before 'indicators' (a question on missing data sources also says "données")
    if any(k in low for k in _KW["sources"]) and any(w in low for w in ("غير متوفر", "مصادر", "source", "manquant", "missing", "indisponible", "disponibles")):
        return "sources"
    if any(k in low for k in _KW["disparity"]):
        return "disparity"
    if any(k in low for k in _KW["scenario"]):
        return "scenario"
    if any(k in low for k in _KW["indicators"]):
        return "indicators"
    return "search"


def _gn(k: str, lang: str) -> str:
    fr, ar = GOVERNORATES[k]
    return ar if lang == "ar" else fr


def _label(s: int, lang: str) -> str:
    return (STATUS_AR if lang == "ar" else STATUS_FR)[int(s)]


class RuleBasedBackend(AssistantBackend):
    name = "demo-rules"

    def answer(self, question: str, lang: str, ctx: dict) -> Answer:
        gov: pd.DataFrame = ctx["gov"]
        cat: pd.DataFrame = ctx["catalog"]
        synthetic: bool = ctx.get("synthetic", True)
        tag = (" (بيانات اصطناعية)" if lang == "ar" else " (données synthétiques)") if synthetic else ""
        intent = _intent(question)
        if intent == "disparity":
            return self._disparity(gov, lang, tag)
        if intent == "scenario":
            return self._scenario(ctx.get("last_sim"), lang, tag)
        if intent == "indicators":
            return self._indicators(cat, lang)
        if intent == "sources":
            return self._sources(cat, lang)
        return self._search(question, cat, lang)

    # ------------------------------------------------------------------
    def _disparity(self, gov, lang, tag) -> Answer:
        if gov["governorate"].nunique() < 24:
            msg = ("التغطية الجهوية غير مكتملة؛ لا يمكن إصدار ترتيب وطني موثوق." if lang == "ar"
                   else "La couverture territoriale est incomplète ; aucun classement national fiable ne peut être produit.")
            return Answer(msg)
        required = ("ptr", "class_size", "equipment_index")
        if any(c not in gov or gov[c].isna().any() for c in required):
            msg = ("لا تتوفر بيانات مكتملة للمؤشرات المطلوبة؛ لم يتم حساب ترتيب اصطناعي بديل." if lang == "ar"
                   else "Les données nécessaires ne sont pas complètes ; aucun classement de substitution n'a été calculé.")
            return Answer(msg)
        z = pd.DataFrame({
            "ptr": (gov["ptr"] - gov["ptr"].mean()) / gov["ptr"].std(),
            "cs": (gov["class_size"] - gov["class_size"].mean()) / gov["class_size"].std(),
            "eq": -(gov["equipment_index"] - gov["equipment_index"].mean()) / gov["equipment_index"].std(),
        })
        gov = gov.assign(resource_gap=z.mean(axis=1))
        top = gov.sort_values("resource_gap", ascending=False).head(5)
        lines = []
        for _, r in top.iterrows():
            k = r["governorate"]
            if lang == "ar":
                lines.append(f"- {_gn(k, lang)}: تلميذ/مدرّس {r['ptr']:.1f}، حجم القسم {r['class_size']:.1f}، التجهيز {r['equipment_index']:.2f}")
            else:
                lines.append(f"- {_gn(k, lang)} : élèves/enseignant {r['ptr']:.1f}, taille de classe {r['class_size']:.1f}, équipement {r['equipment_index']:.2f}")
        spread = gov["ptr"].max() / gov["ptr"].min()
        if lang == "ar":
            head = f"الولايات الخمس الأضعف موارد حسب مؤشر مركّب (تلميذ/مدرّس، حجم القسم، التجهيز){tag}:"
            tail = f"\nنسبة أعلى إلى أدنى تلميذ/مدرّس بين الولايات: {spread:.2f}. المؤشر مركّب بسيط (متوسط الدرجات المعيارية) ولا يُستعمل للتصنيف الرسمي."
        else:
            head = f"Les cinq gouvernorats les moins dotés selon un indice composite (élèves/enseignant, taille de classe, équipement){tag} :"
            tail = f"\nRapport max/min des élèves par enseignant entre gouvernorats : {spread:.2f}. Indice composite simple (moyenne de scores z), à ne pas utiliser pour un classement officiel."
        return Answer(head + "\n" + "\n".join(lines) + tail, [("Table des gouvernorats de la plateforme", "", "synthétique" if tag else "données importées")])

    def _scenario(self, sim, lang, tag) -> Answer:
        if not sim:
            msg = ("لم يُشغَّل أي سيناريو بعد. افتح «مختبر محاكاة السياسات»، اضبط الفرضيات ثم اسألني من جديد." if lang == "ar"
                   else "Aucun scénario n'a encore été exécuté. Ouvrez le « Laboratoire de simulation », réglez les hypothèses puis reposez la question.")
            return Answer(msg)
        n, c, s = sim["national"], sim["costs"], sim["scenario"]
        if lang == "ar":
            t = (f"السيناريو الحالي{tag}: تخفيض حجم القسم {s['class_size_reduction'] * 100:.0f}%، مدرّسون إضافيون {s['extra_teachers_pct']:.1f}%، تجهيز {s['equipment_budget_um']:,.0f} و.ك، وزن الإنصاف {s['equity_weight']:.0%}.\n"
                 f"- حجم القسم الوطني: {n['class_size_before']:.1f} ← {n['class_size_after']:.1f}\n- تلميذ/مدرّس: {n['ptr_before']:.1f} ← {n['ptr_after']:.1f}\n"
                 f"- جودة التعلمات (مؤشر 0-100): {n['quality_before']:.1f} ← {n['quality_after']:.1f} (Δ {n['delta_quality']:+.2f})\n- الفجوة بين الربع الأعلى والأدنى: {n['gap_before']:.2f} ← {n['gap_after']:.2f}\n"
                 f"- الكلفة على أفق {c['horizon_years']} سنوات: {c['horizon_total_um']:,.0f} وحدة كلفة (و.ك = كلفة مدرّس لسنة).\n"
                 "تنبيه: النتائج محاكاة حسابية بمعاملات غير معايرة؛ راجع نطاق الشك في صفحة المختبر.")
        else:
            t = (f"Scénario actuel{tag} : réduction de la taille des classes {s['class_size_reduction'] * 100:.0f} %, enseignants supplémentaires {s['extra_teachers_pct']:.1f} %, équipement {s['equipment_budget_um']:,.0f} UC, poids d'équité {s['equity_weight']:.0%}.\n"
                 f"- Taille de classe nationale : {n['class_size_before']:.1f} → {n['class_size_after']:.1f}\n- Élèves/enseignant : {n['ptr_before']:.1f} → {n['ptr_after']:.1f}\n"
                 f"- Qualité des apprentissages (indice 0-100) : {n['quality_before']:.1f} → {n['quality_after']:.1f} (Δ {n['delta_quality']:+.2f})\n- Écart quartile haut/bas : {n['gap_before']:.2f} → {n['gap_after']:.2f}\n"
                 f"- Coût sur {c['horizon_years']} ans : {c['horizon_total_um']:,.0f} unités de coût (UC = coût d'un enseignant-année).\n"
                 "Attention : simulation arithmétique à paramètres non calibrés ; voir la fourchette d'incertitude dans le laboratoire.")
        return Answer(t, [("Policy Simulation Lab (session courante)", "", "calcul local")])

    def _indicators(self, cat, lang) -> Answer:
        rows = [
            ("class_size_ptr", ("حجم القسم وعدد التلاميذ لكل مدرّس (جهوياً)", "Taille de classe et élèves/enseignant (régional)"), "MEN-03"),
            ("dropout", ("الانقطاع المدرسي حسب الجهة والمرحلة", "Abandon scolaire par région et cycle"), "INS-02"),
            ("learning", ("نتائج التعلمات الموحّدة", "Résultats d'apprentissage standardisés"), "EVAL-01"),
            ("exams", ("مطابقة الامتحانات للبرامج (بلوم)", "Alignement examens/programmes (Bloom)"), "MEN-05"),
            ("budget", ("تنفيذ ميزانية التربية جهوياً", "Exécution régionale du budget de l'éducation"), "MOF-04"),
            ("infra", ("حالة البنية التحتية والتجهيز", "État du bâti et des équipements"), "MEN-06"),
            ("equity", ("الأمية والمزاولة حسب الولاية", "Analphabétisme et scolarisation par gouvernorat"), "INS-01"),
        ]
        out = []
        srcs = []
        for _k, (ar, fr), cid in rows:
            r = cat[cat["id"] == cid].iloc[0]
            lbl = ar if lang == "ar" else fr
            out.append(f"- {lbl} — {_label(r['status'], lang)} [{cid}]")
            srcs.append((r["name_ar"] if lang == "ar" else r["name_fr"], r["url"] if isinstance(r["url"], str) else "", _label(r["status"], lang)))
        head = ("مؤشرات مقترحة للمجلس مع حالة توفر البيانات التي تغذيها (اقتراح تحليلي وليس قراراً رسمياً):" if lang == "ar"
                else "Indicateurs proposés au Conseil avec le statut des données qui les alimentent (proposition analytique, pas une décision officielle) :")
        return Answer(head + "\n" + "\n".join(out), srcs)

    def _sources(self, cat, lang) -> Answer:
        miss = cat[cat["status"].isin([3, 4])].sort_values("status", ascending=False)
        col = "name_ar" if lang == "ar" else "name_fr"
        lines = [f"- [{r['id']}] {r[col]} — {_label(r['status'], lang)}" for _, r in miss.iterrows()]
        head = (f"مصادر لم تتأكد إتاحتها بعد ({len(miss)} من {len(cat)}):" if lang == "ar" else f"Sources dont l'accessibilité n'est pas confirmée ({len(miss)} sur {len(cat)}) :")
        foot = ("\nالحالة 3 تعني وجوداً مرجحاً داخلياً يحتاج إلى تأكيد الجهة المالكة؛ الحالة 4 تعني عدم العثور على مصدر موثق." if lang == "ar"
                else "\nStatut 3 = existence probable en interne à confirmer auprès du propriétaire ; statut 4 = aucune source documentée trouvée.")
        return Answer(head + "\n" + "\n".join(lines) + foot, [("data_sources.csv (matrice des sources)", "", "recherche du 14/11/2026")])

    def _search(self, q, cat, lang) -> Answer:
        tokens = [t for t in q.lower().replace("؟", " ").replace("?", " ").split() if len(t) > 2]
        hay = (cat["name_ar"] + " " + cat["name_fr"] + " " + cat["owner_fr"] + " " + cat["constraints_fr"] + " " + cat["constraints_ar"]).str.lower()
        score = hay.map(lambda h: sum(t in h for t in tokens))
        hits = cat[score > 0].assign(score=score[score > 0]).sort_values("score", ascending=False).head(3)
        if hits.empty:
            msg = ("وضع تجريبي بلا نموذج لغوي: لا أستطيع الإجابة عن هذا السؤال بشكل موثوق. الأسئلة المدعومة: الولايات الأكثر تفاوتاً في الموارد، أثر السيناريو الحالي، المؤشرات التي يجب مراقبتها، المصادر غير المتوفرة. يمكنني أيضاً البحث في مصفوفة المصادر بكلمات مفتاحية."
                   if lang == "ar" else
                   "Mode démonstration sans modèle de langage : je ne peux pas répondre de façon fiable à cette question. Questions prises en charge : gouvernorats les plus inégaux en ressources, effet du scénario courant, indicateurs à suivre, sources non disponibles. Je peux aussi chercher dans la matrice des sources par mots-clés.")
            return Answer(msg)
        col = "name_ar" if lang == "ar" else "name_fr"
        lines = [f"- [{r['id']}] {r[col]} — {_label(r['status'], lang)}" for _, r in hits.iterrows()]
        head = "نتائج بحث نصي في مصفوفة المصادر (لا تحليل):" if lang == "ar" else "Résultats d'une recherche textuelle dans la matrice des sources (sans analyse) :"
        return Answer(head + "\n" + "\n".join(lines), [(r[col], r["url"] if isinstance(r["url"], str) else "", _label(r["status"], lang)) for _, r in hits.iterrows()])

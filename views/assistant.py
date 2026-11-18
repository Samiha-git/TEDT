import streamlit as st

import ui
from tedt_core import data_store
from tedt_core.assistant import RuleBasedBackend
from ui import L

BACKEND = RuleBasedBackend()


def _ask(q: str, bundle):
    ctx = {"gov": bundle.governorates(), "catalog": data_store.load_catalog(), "synthetic": ui.is_synthetic(bundle), "last_sim": st.session_state.get("last_sim")}
    ans = BACKEND.answer(q, ui.lang(), ctx)
    st.session_state.setdefault("chat", []).append({"role": "user", "text": q})
    st.session_state["chat"].append({"role": "assistant", "text": ans.text, "sources": ans.sources, "mode": ans.mode})


def render():
    bundle = ui.get_bundle()
    ui.page_title(L("المساعد الذكي للسياسات", "Assistant de politiques publiques"), "chat")
    st.warning(L("**وضع تجريبي بلا نموذج لغوي.** لا يوجد ذكاء اصطناعي توليدي متصل: الإجابات مبنية على قواعد ثابتة وجداول المنصة ومصفوفة المصادر، وتُرفَق بها المصادر وحالتها. لا تُقدَّم أي معلومة غير موثقة كحقيقة. التكامل مع نموذج لغوي وبحث دلالي في الوثائق الرسمية مرحلة لاحقة (انظر README).",
                 "**Mode démonstration sans modèle de langage.** Aucune IA générative n'est connectée : les réponses reposent sur des règles fixes, les tables de la plateforme et la matrice des sources, avec leurs sources et leur statut. Aucune information non documentée n'est présentée comme un fait. L'intégration d'un LLM et d'une recherche sémantique dans les documents officiels est une phase ultérieure (voir README)."))
    ui.banner(bundle)

    suggestions = [
        L("ما الولايات التي تسجل أكبر تفاوت في الموارد التعليمية؟", "Quels gouvernorats présentent le plus d'inégalités de ressources éducatives ?"),
        L("ما أثر تخفيف الاكتظاظ وفق السيناريو المختار؟", "Quel est l'effet de la réduction de la surcharge selon le scénario choisi ?"),
        L("ما أهم المؤشرات التي يجب أن يراقبها المجلس؟", "Quels sont les principaux indicateurs que le Conseil devrait suivre ?"),
        L("ما مصادر البيانات التي ما زالت غير متوفرة؟", "Quelles sources de données ne sont pas encore disponibles ?"),
    ]
    cols = st.columns(2)
    for i, s in enumerate(suggestions):
        if cols[i % 2].button(s, key=f"as_sug_{i}", width="stretch"):
            _ask(s, bundle)
    q = st.chat_input(L("اطرح سؤالك…", "Posez votre question…"), key="as_input")
    if q:
        _ask(q, bundle)
    for msg in st.session_state.get("chat", []):
        with st.chat_message(msg["role"]):
            st.markdown(msg["text"])
            if msg["role"] == "assistant":
                if msg.get("sources"):
                    with st.expander(L("المصادر وحالتها", "Sources et statut")):
                        for title, url, status in msg["sources"]:
                            st.markdown(f"- {title} — *{status}*" + (f" — {url}" if url else ""))
                st.caption(L("وضع: قواعد تجريبية (بلا نموذج لغوي)", "Mode : règles de démonstration (sans LLM)"))
    if st.session_state.get("chat") and st.button(L("مسح المحادثة", "Effacer la conversation"), key="as_clear"):
        st.session_state["chat"] = []
        st.rerun()

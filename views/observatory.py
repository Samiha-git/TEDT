import io

import pandas as pd
import plotly.express as px
import streamlit as st

import ui
from tedt_core import scenario_store, security, foundation
from tedt_core import data_store
from tedt_core.config import PALETTE
from ui import L

STATUS_LABELS = {
    1: ("1 — متوفر ومثبت بمصدر", "1 — Disponible et sourcé"),
    2: ("2 — متوفر جزئياً", "2 — Partiellement disponible"),
    3: ("3 — يُحتمل وجوده داخلياً (يلزم تأكيد)", "3 — Probable en interne (à confirmer)"),
    4: ("4 — غير متوفر / لم يُتحقق منه", "4 — Indisponible / non vérifié"),
}


def _template(kind: str) -> bytes:
    sc = data_store.SCHEMAS[kind]
    cols = sc["required"] + sc["optional"]
    return pd.DataFrame(columns=cols).to_csv(index=False).encode("utf-8")


def render():
    bundle = ui.get_bundle()
    ui.page_title(L("مرصد البيانات التربوية", "Observatoire des données éducatives"), "db")
    ui.banner(bundle)
    t_cat, t_active, t_import, t_foundation = st.tabs([L("مصفوفة المصادر", "Matrice des sources"), L("قواعد البيانات النشطة", "Jeux de données actifs"), L("استيراد Lot 0", "Imports Lot 0"), L("أساس البيانات — Lot 1", "Socle de données — Lot 1")])

    with t_cat:
        cat = data_store.load_catalog()
        st.markdown(L("نتائج البحث الوثائقي بتاريخ 14/11/2026. **لا تعني الإحصائيات المنشورة أن قاعدة البيانات الداخلية متاحة.**",
                      "Résultats de la recherche documentaire au 14/11/2026. **Des statistiques publiées n'impliquent pas que la base interne soit accessible.**"))
        counts = cat["status"].value_counts().reindex([1, 2, 3, 4]).fillna(0).astype(int)
        ui.cards([(L(STATUS_LABELS[s][0], STATUS_LABELS[s][1]), str(counts[s]), "") for s in (1, 2, 3, 4)])
        c1, c2 = st.columns(2)
        sel = c1.multiselect(L("حالة التحقق", "Statut"), [1, 2, 3, 4], default=[1, 2, 3, 4], format_func=lambda s: L(*STATUS_LABELS[s]), key="obs_status")
        owners = sorted(cat["owner_fr"].unique())
        own = c2.multiselect(L("الجهة المالكة", "Propriétaire"), owners, key="obs_owner")
        view = cat[cat["status"].isin(sel)]
        if own:
            view = view[view["owner_fr"].isin(own)]
        ar = ui.lang() == "ar"
        show = pd.DataFrame({
            L("المجموعة", "Jeu de données"): view["name_ar" if ar else "name_fr"],
            L("الجهة المالكة", "Propriétaire"): view["owner_ar" if ar else "owner_fr"],
            L("مستوى التفصيل", "Granularité"): view["granularity_ar" if ar else "granularity_fr"],
            L("السنوات", "Années"): view["years"],
            L("التحيين", "Fréquence"): view["frequency"],
            L("الصيغة", "Format"): view["format"],
            L("إمكانية الربط", "Liaison possible"): view["linkability"],
            L("القيود", "Contraintes"): view["constraints_ar" if ar else "constraints_fr"],
            L("الحالة", "Statut"): view["status"].map(lambda s: L(*STATUS_LABELS[s])),
            L("تاريخ المصدر", "Date source"): view["source_date"].fillna(""),
            L("الرابط", "Lien"): view["url"].fillna(""),
        })
        st.dataframe(show, hide_index=True, width="stretch", column_config={L("الرابط", "Lien"): st.column_config.LinkColumn()})
        st.download_button(L("تنزيل المصفوفة (CSV)", "Télécharger la matrice (CSV)"), view.to_csv(index=False).encode("utf-8-sig"), "tedt_data_sources.csv", "text/csv", key="obs_dl_cat")
        fig = px.pie(counts.reset_index(), names=counts.index.map(lambda s: L(*STATUS_LABELS[s])), values="count", hole=0.5,
                     color_discrete_sequence=[PALETTE["olive"], PALETTE["blue_light"], PALETTE["gold"], PALETTE["grey"]])
        st.plotly_chart(ui.style_fig(fig, 320), width="stretch")
        st.caption(L("مؤشر الجاهزية الوثائقية = متوسط أوزان الحالات (1→1.0، 2→0.6، 3→0.25، 4→0). يقيس ما هو موثّق لا جودة البيانات.",
                     "Indice de préparation documentaire = moyenne des poids de statut (1→1,0 ; 2→0,6 ; 3→0,25 ; 4→0). Il mesure ce qui est documenté, pas la qualité des données."))

    with t_active:
        rows = []
        for name, df in (("institutions", bundle.institutions), ("results", bundle.results), ("exam_items", bundle.exam_items), ("curriculum", bundle.curriculum), ("students", bundle.students)):
            prov = bundle.provenance.get(name, "synthetic")
            comp = df.notna().mean().mean() * 100
            rows.append({
                L("المجموعة", "Jeu de données"): name, L("الأصل", "Origine"): L("اصطناعي", "Synthétique") if prov == "synthetic" else (L("مستورد — المصدر غير معتمد", "Importé — source non certifiée") if prov == "imported_unverified" else L("غير متاح", "Indisponible")),
                L("الصفوف", "Lignes"): len(df), L("الأعمدة", "Colonnes"): df.shape[1],
                L("اكتمال البيانات %", "Complétude %"): round(comp, 1) if prov not in ("synthetic", "unavailable") else None,
                L("آخر تحديث", "Dernière mise à jour"): L("مولّدة عند التشغيل", "Générées au lancement") if prov == "synthetic" else st.session_state.get("override_meta", {}).get(name, ""),
            })
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        st.caption(L("الاكتمال غير معروض للبيانات الاصطناعية لأنه 100% بالبناء ولا معنى له.", "La complétude n'est pas affichée pour les données synthétiques (100 % par construction, sans signification)."))
        meta = st.session_state.get("override_report", {})
        for name, rep in meta.items():
            st.markdown(f"**{name}** — {L('درجة الجودة', 'score de qualité')}: {rep['score']:.1f}/100")
            st.dataframe(rep["completeness"], hide_index=True, width="stretch")

    with t_import:
        if bundle.mode != "REAL_DATA":
            st.info(L("اختر وضع البيانات الحقيقية من الشريط الجانبي قبل اعتماد ملف مستورد. لن تُستخدم الملفات المستوردة في وضع العرض التوضيحي.", "Sélectionnez le mode Données réelles dans la barre latérale avant d’activer un fichier importé. Les imports ne sont jamais utilisés en mode démonstration."))
        elif not ui.can_import_dataset():
            st.warning(L("اعتماد البيانات الحقيقية يتطلب جلسة موثقة بدور محلل أو مدير. لا يوجد تسجيل دخول مؤسسي مفعّل في هذه النسخة.", "L’activation des données réelles exige une session authentifiée avec rôle analyste ou administrateur. Aucun système de connexion institutionnel n’est activé dans cette version."))
        kind = st.selectbox(L("نوع الملف", "Type de fichier"), list(data_store.SCHEMAS), format_func=lambda k: {"institutions": L("المؤسسات التربوية", "Établissements"), "results": L("النتائج", "Résultats")}[k], key="imp_kind")
        sc = data_store.SCHEMAS[kind]
        st.markdown(L("**الأعمدة المطلوبة:** ", "**Colonnes requises :** ") + ", ".join(sc["required"]))
        st.markdown(L("**اختيارية:** ", "**Optionnelles :** ") + ", ".join(sc["optional"]))
        st.caption(sc["help"])
        st.caption(L("أسماء الولايات تُقبل بالعربية أو الفرنسية. لا ترفع بيانات شخصية: المنصة مصممة لبيانات مجمّعة على مستوى المؤسسة.",
                     "Les noms de gouvernorats sont acceptés en arabe ou en français. N'importez pas de données personnelles : la plateforme est conçue pour des données agrégées par établissement."))
        st.download_button(L("تنزيل قالب فارغ", "Télécharger un modèle vide"), _template(kind), f"tedt_template_{kind}.csv", "text/csv", key="imp_tpl")
        up = st.file_uploader(L("ملف CSV أو Excel", "Fichier CSV ou Excel"), type=["csv", "xlsx", "xls"], key=f"imp_file_{kind}")
        if up is not None:
            try:
                df = data_store.read_uploaded(up)
            except Exception as e:  # noqa: BLE001
                st.error(f"{L('تعذّرت قراءة الملف', 'Lecture impossible')}: {e}")
                df = None
            if df is not None:
                st.write(L("معاينة", "Aperçu"), df.head(8))
                rep = data_store.validate_dataset(kind, df)
                for e in rep.errors:
                    st.error(e)
                for w in rep.warnings:
                    st.warning(w)
                if not rep.rejected.empty:
                    st.download_button(L("تنزيل الملاحظات المرفوضة CSV", "Exporter les observations rejetées (CSV)"),
                                       rep.rejected.assign(__tedt_mode="REAL_DATA", __tedt_provenance="user_upload_unverified", __tedt_warning="SOURCE_NOT_CERTIFIED").to_csv(index=False).encode("utf-8-sig"),
                                       f"tedt_rejected_{kind}.csv", "text/csv", key=f"imp_rejected_{kind}")
                if rep.ok:
                    st.success(L(f"تم التحقق: {len(rep.clean)} صف صالح، درجة الجودة {rep.quality_score:.1f}/100", f"Validé : {len(rep.clean)} lignes valides, score de qualité {rep.quality_score:.1f}/100"))
                    st.caption(L(f"المدخلات: {rep.counts.get('input', 0)} · المقبول: {rep.counts.get('accepted', 0)} · المرفوض: {rep.counts.get('rejected', 0)}", f"Entrées : {rep.counts.get('input', 0)} · acceptées : {rep.counts.get('accepted', 0)} · rejetées : {rep.counts.get('rejected', 0)}"))
                    st.dataframe(rep.completeness, hide_index=True, width="stretch")
                    if not rep.rejected.empty:
                        st.warning(L("توجد ملاحظات مرفوضة؛ تمت إتاحة ملفها للمراجعة.", "Des observations ont été rejetées ; leur fichier est disponible pour examen."))
                    if st.button(L("اعتماد الملف كبيانات نشطة", "Utiliser ce fichier comme jeu actif"), key=f"imp_apply_{kind}", type="primary", disabled=(bundle.mode != "REAL_DATA" or not ui.can_import_dataset())):
                        st.session_state.setdefault("overrides", {})[kind] = rep.clean
                        st.session_state.setdefault("override_meta", {})[kind] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
                        st.session_state.setdefault("override_report", {})[kind] = {"score": rep.quality_score, "completeness": rep.completeness, "counts": rep.counts, "rejected": rep.rejected}
                        ident = security.identity(st.session_state)
                        scenario_store.log_event("aggregate_dataset_imported", ident["user_id"], {"dataset": kind, "rows": len(rep.clean), "quality_score": rep.quality_score})
                        st.rerun()
        if st.session_state.get("overrides"):
            if st.button(L("مسح الملفات المستوردة", "Effacer les fichiers importés"), key="imp_reset"):
                for k in ("overrides", "override_meta", "override_report"):
                    st.session_state.pop(k, None)
                st.rerun()
        st.info(L("يمكن أيضاً وضع الملفات في المجلد data/official لاحقاً ضمن تكامل مؤسسي (انظر README).", "Les fichiers peuvent aussi être déposés dans data/official lors d'une intégration institutionnelle (voir README)."))

    with t_foundation:
        st.subheader(L("سجل الدفعات وجودة البيانات", "Registre des lots et qualité des données"))
        try:
            foundation.seed_reference_files()
            sources_df = pd.read_csv(foundation.SOURCE_REGISTER).fillna("")
            indicators_df = pd.read_csv(foundation.INDICATOR_DICTIONARY).fillna("")
            st.markdown(L("**سجل المصادر — 6 حالات تحقق**", "**Registre des sources — 6 statuts de disponibilité**"))
            source_display = sources_df[["source_id", "source_name", "owner", "families", "geographic_coverage", "temporal_coverage", "format", "status_code", "status_label", "access_conditions", "verification_note", "url", "direct_download_url"]]
            st.dataframe(source_display, hide_index=True, width="stretch", column_config={"url": st.column_config.LinkColumn(), "direct_download_url": st.column_config.LinkColumn()})
            st.markdown(L("**القاموس الأولي للمؤشرات**", "**Dictionnaire initial des indicateurs**"))
            st.dataframe(indicators_df, hide_index=True, width="stretch")
            summary = foundation.quality_summary()
            if summary["total_batches"] == 0:
                st.info(L("لا توجد دفعات importées dans le staging. Le socle est initialisé, mais aucune source n'a encore été chargée.",
                          "Aucun lot n'a encore été importé dans la zone de staging. Le socle est initialisé, mais aucune source n'a été chargée."))
            else:
                state_counts = summary["by_state"]
                ui.cards([(str(k), str(v), "") for k, v in state_counts.items()])
                st.dataframe(summary["batches"], hide_index=True, width="stretch")
                if not summary.get("variable_quality", pd.DataFrame()).empty:
                    st.markdown(L("**الاكتمال حسب المتغير**", "**Complétude par variable**"))
                    st.dataframe(summary["variable_quality"], hide_index=True, width="stretch")
                if not summary["issues"].empty:
                    st.markdown(L("**الأخطاء والتنبيهات**", "**Anomalies et avertissements**"))
                    st.dataframe(summary["issues"], hide_index=True, width="stretch")
                st.caption(summary.get("missing_periods_note", ""))
            st.markdown("---")
            st.subheader(L("استيراد عام إلى منطقة staging", "Import générique vers la zone de staging"))
            st.caption(L("يُحفظ الملف الأصلي دون تعديل مع بصمة SHA-256 وبيانات المصدر. لا يتم تحميله تلقائياً إلى مستودع البيانات.",
                         "Le fichier original est conservé sans modification avec son empreinte SHA-256 et ses métadonnées. Il n'est pas chargé automatiquement dans l'entrepôt."))
            if bundle.mode != "REAL_DATA":
                st.warning(L("هذا المسار متاح فقط في وضع البيانات الحقيقية.", "Ce circuit est réservé au mode REAL_DATA."))
            if not ui.can_import_dataset():
                st.warning(L("يتطلب الاستيراد جلسة موثقة بدور محلل أو مدير. لا يوجد SSO institutionnel raccordé dans cette version.",
                             "L'import exige une session authentifiée analyste ou administrateur. Aucun SSO institutionnel n'est raccordé dans cette version."))
            source_options = sources_df["source_id"].tolist()
            source_labels = {r["source_id"]: f"{r['source_id']} — {r['source_name']}" for r in sources_df.to_dict("records")}
            with st.form("foundation_ingest_form"):
                selected_source = st.selectbox(L("المصدر", "Source"), source_options, format_func=lambda x: source_labels.get(x, x))
                source_row = sources_df[sources_df["source_id"] == selected_source].iloc[0]
                dataset_code = st.text_input(L("رمز مجموعة البيانات", "Code du jeu de données"), value="INS_RGPH24_SCHOOLING_6_14" if selected_source == "INS-RGPH24-EDU-01" else selected_source.replace("-", "_"))
                source_title = st.text_input(L("عنوان المصدر", "Titre du jeu"), value=str(source_row["source_name"]))
                source_reference = st.text_input(L("مرجع المصدر / الرابط", "Référence ou URL de la source"), value=str(source_row["url"]))
                c1, c2 = st.columns(2)
                period_start = c1.text_input(L("بداية الفترة", "Début de période"), value=str(source_row["temporal_coverage"]) if str(source_row["temporal_coverage"]) not in ("", "nan") else "à préciser")
                period_end = c2.text_input(L("نهاية الفترة", "Fin de période"), value=str(source_row["temporal_coverage"]) if str(source_row["temporal_coverage"]) not in ("", "nan") else "à préciser")
                c3, c4 = st.columns(2)
                geographic_level = c3.selectbox(L("المستوى الجغرافي", "Niveau géographique"), ["national", "governorate", "delegation", "institution", "unknown"], index=1)
                granularity = c4.text_input(L("درجة التفصيل", "Granularité"), value=str(source_row["granularity"]))
                c5, c6 = st.columns(2)
                source_owner = c5.text_input(L("المؤسسة المالكة", "Institution propriétaire"), value=str(source_row["owner"]))
                language = c6.selectbox(L("اللغة", "Langue"), ["fr", "ar", "en", "multiple", "unknown"])
                authorization = st.text_input(L("الترخيص أو الإذن المعلن", "Licence ou autorisation déclarée"), value="Publication publique ; conditions de réutilisation à vérifier")
                classification = st.selectbox(L("تصنيف الأمان", "Classification de sécurité"), ["PUBLIC", "INSTITUTIONAL_NON_SENSITIVE"])
                schema_version = st.text_input(L("نسخة المخطط", "Version du schéma"), value="1.0")
                uploaded = st.file_uploader(L("ملف CSV أو XLSX", "Fichier CSV ou XLSX"), type=["csv", "xlsx"], key="foundation_file")
                submitted = st.form_submit_button(L("حفظ الملف الأصلي في staging", "Conserver le fichier original dans le staging"), type="primary", disabled=(bundle.mode != "REAL_DATA" or not ui.can_import_dataset()))
            if submitted:
                if uploaded is None:
                    st.error(L("يرجى اختيار ملف.", "Veuillez sélectionner un fichier."))
                else:
                    try:
                        ident = security.identity(st.session_state)
                        metadata = {
                            "source_id": selected_source, "dataset_code": dataset_code.strip(),
                            "source_owner": source_owner, "source_title": source_title,
                            "source_reference": source_reference, "reference_period_start": period_start,
                            "reference_period_end": period_end, "geographic_level": geographic_level,
                            "granularity": granularity, "declared_license_or_authorization": authorization,
                            "security_classification": classification, "language": language,
                            "schema_version": schema_version,
                        }
                        result = foundation.ingest_file(uploaded.name, uploaded.getvalue(), metadata, received_by=ident["user_id"])
                        st.session_state["foundation_last_batch"] = result["batch_id"]
                        st.success(L(f"تم حفظ الدفعة {result['batch_id']} دون تحميلها إلى المستودع.", f"Lot {result['batch_id']} conservé dans le staging, sans chargement dans l'entrepôt."))
                        st.code(result["sha256"], language="text")
                        st.dataframe(result["preview"], hide_index=True, width="stretch")
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"{L('تعذر الاستيراد', 'Import impossible')} : {exc}")
            last_batch = st.session_state.get("foundation_last_batch")
            if last_batch:
                st.markdown("---")
                st.markdown(L("**التحقق الهيكلي للدفعة الأخيرة**", "**Contrôle structurel du dernier lot**"))
                required_text = st.text_input(L("الأعمدة المطلوبة (اختياري، مفصولة بفواصل)", "Colonnes obligatoires (facultatif, séparées par des virgules)"), key="foundation_required_columns")
                if st.button(L("تشغيل التحقق الهيكلي", "Lancer le contrôle structurel"), key="foundation_validate_batch"):
                    result = foundation.validate_batch(last_batch, required_columns=[x.strip() for x in required_text.split(",") if x.strip()])
                    st.session_state["foundation_last_validation"] = result
                    if result["status"] == "VALIDATED":
                        st.success(L("التحقق الهيكلي ناجح. لم يتم بعد اعتماد المطابقة الدلالية أو تحميل البيانات.", "Contrôle structurel réussi. La conformité sémantique n'est pas encore approuvée et les données ne sont pas chargées."))
                    else:
                        st.error(L("تم رفض الدفعة: يجب معالجة الأخطاء قبل المتابعة.", "Lot rejeté : corrigez les anomalies avant de poursuivre."))
                    st.json(result["quality"])
                    for issue in result["errors"] + result["warnings"]:
                        (st.error if issue["severity"] == "ERROR" else st.warning)(issue["message"])
        except Exception as exc:  # noqa: BLE001
            st.error(f"{L('تعذر فتح socle de données', 'Impossible d’ouvrir le socle de données')} : {exc}")

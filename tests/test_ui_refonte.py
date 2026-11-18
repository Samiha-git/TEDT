"""Smoke tests for the presentation layer (horizontal navigation, 8 modules, FR/AR, data modes)."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest


def _run(lang="fr", mode="DEMONSTRATION"):
    at = AppTest.from_file(str(Path(__file__).resolve().parent.parent / "app.py"), default_timeout=120)
    at.session_state["lang"] = lang
    at.session_state["data_mode"] = mode
    at.run()
    return at


@pytest.mark.parametrize("lang", ["fr", "ar"])
def test_home_renders_without_exception(lang):
    at = _run(lang)
    assert not at.exception, at.exception
    html = " ".join(m.value for m in at.markdown)
    assert "tedt-brand-header" in html and "tedt-kpi" in html and "tedt-hero" in html


def test_no_sidebar_widgets():
    at = _run("fr")
    assert len(at.sidebar.children) == 0


def test_language_and_mode_widgets_exist():
    at = _run("fr")
    assert at.radio(key="lang").value == "fr"
    assert at.selectbox(key="data_mode_ui_fr").value == "DEMONSTRATION"


def test_real_data_mode_blocks_modules_without_synthetic_substitution():
    at = _run("fr", "REAL_DATA")
    assert not at.exception, at.exception
    assert any("Module bloqué" in w.value for w in at.warning)

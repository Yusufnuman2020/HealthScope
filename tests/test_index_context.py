# -*- coding: utf-8 -*-
"""Klinik indekslerin bağlama duyarlılığı — gerçek vaka regresyonu.

Kaynak vaka: 22 yaş erkek, Bolu İzzet Baysal DH, 22.07.2026.
    AST 368, ALT 115, GGT 15 (normal), ALP 86, bilirubin ve albümin normal,
    kreatinin 1.41.

Uygulama De Ritis 3.2 hesaplayıp "alkolik karaciğer hastalığı paterni" demişti.
Hastayı gören hekim aynı hipotezi kurdu, sonra GGT'nin normal olduğunu görüp
eledi ve tabloyu protein/kreatin takviyesine (kas kaynaklı AST artışı) bağladı.

Bu testler, motorun aynı ayrımı yapabildiğini garanti eder.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import catalog as catalog_module  # noqa: E402
import config  # noqa: E402
import indices as indices_module  # noqa: E402


@pytest.fixture(scope="module")
def cat():
    return catalog_module.load(config.DATABASE_PATH)


#: Gerçek vakanın ilgili değerleri.
CASE = {
    "ast": 368.0, "alt": 115.0, "ggt": 15.0, "alp": 86.0, "plt": 213.0,
    "kreatinin": 1.41, "ure": 35.0, "neu": 9.1, "lym": 0.8,
    "sodyum": 139.0, "glukoz": 109.0,
}
BIO = {"yas": 22, "cinsiyet": "male"}


def compute(cat, values=None, bio=None):
    computed, _ = indices_module.compute(
        cat.indices, values or CASE, bio or BIO, cat
    )
    return {item["id"]: item for item in computed}


# ── De Ritis: GGT bağlamı ─────────────────────────────────────────────────
def test_de_ritis_with_normal_ggt_points_to_muscle_not_alcohol(cat):
    """Asıl regresyon: GGT normalken 'alkolik' yorumu verilmemeli."""
    de_ritis = compute(cat)["de_ritis"]
    assert de_ritis["value"] == pytest.approx(3.2, abs=0.05)
    assert "alkol" not in de_ritis["interpretation"].lower() or "olası değil" in de_ritis["interpretation"].lower()
    assert "kas" in de_ritis["interpretation"].lower()
    # Bastırılan ham yorum şeffaflık için korunmalı
    assert de_ritis["overridden_interpretation"] is not None
    assert "alkolik" in de_ritis["overridden_interpretation"].lower()


def test_de_ritis_suggests_ck_as_discriminating_test(cat):
    """Kas mı karaciğer mi sorusunu CK çözer; motor bunu önermeli."""
    de_ritis = compute(cat)["de_ritis"]
    assert "ck" in de_ritis["suggested_tests"]


def test_de_ritis_keeps_alcohol_interpretation_when_ggt_is_high(cat):
    """GGT yüksekse alkolik patern yorumu KORUNMALI — düzeltici körlemesine çalışmamalı."""
    values = {**CASE, "ggt": 285.0}
    de_ritis = compute(cat, values)["de_ritis"]
    assert "alkolik" in de_ritis["interpretation"].lower()
    assert de_ritis["overridden_interpretation"] is None


# ── FIB-4: yaş geçerliliği ────────────────────────────────────────────────
def test_fib4_is_caveated_for_young_patient(cat):
    fib4 = compute(cat)["fib4"]
    assert fib4["level"] == "borderline"
    assert "35 yaş altında" in fib4["interpretation"]
    assert fib4["overridden_interpretation"] is not None


def test_fib4_keeps_normal_result_uncaveated(cat):
    """Genç ama FIB-4'ü normal olan hastada uyarı ÇIKMAMALI (when_level koruması)."""
    values = {**CASE, "ast": 30.0, "alt": 28.0, "plt": 250.0}
    fib4 = compute(cat, values)["fib4"]
    assert fib4["level"] == "normal"
    assert fib4["overridden_interpretation"] is None


def test_fib4_uncaveated_for_older_patient(cat):
    fib4 = compute(cat, bio={"yas": 58, "cinsiyet": "male"})["fib4"]
    assert "35 yaş altında" not in fib4["interpretation"]


# ── eGFR: kas kütlesi bağlamı ─────────────────────────────────────────────
def test_egfr_notes_muscle_mass_confound_in_young_male(cat):
    egfr = compute(cat)["egfr"]
    assert "kas kütlesi" in egfr["interpretation"]
    assert egfr["overridden_interpretation"] is not None


def test_egfr_uncaveated_in_older_patient(cat):
    egfr = compute(cat, bio={"yas": 70, "cinsiyet": "male"})["egfr"]
    assert "kas kütlesi" not in egfr["interpretation"]


# ── Test önerilerinin toplanması ──────────────────────────────────────────
def test_collect_suggested_tests_resolves_catalog_labels(cat):
    computed, _ = indices_module.compute(cat.indices, CASE, BIO, cat)
    tests = indices_module.collect_suggested_tests(computed, cat)
    by_id = {t["id"]: t for t in tests}

    assert "ck" in by_id
    assert by_id["ck"]["in_catalog"] is True
    assert by_id["ck"]["label"] == cat.get("ck").label
    assert "De Ritis" in by_id["ck"]["reason"]

    # Katalogda olmayan öneriler de yazıldığı gibi geçmeli
    assert any(not t["in_catalog"] for t in tests)


def test_healthy_patient_gets_no_test_suggestions(cat):
    healthy = {
        "ast": 22.0, "alt": 24.0, "ggt": 25.0, "plt": 250.0, "kreatinin": 0.9,
        "ure": 30.0, "neu": 4.0, "lym": 2.2, "sodyum": 140.0, "glukoz": 88.0,
    }
    computed, _ = indices_module.compute(cat.indices, healthy, {"yas": 29, "cinsiyet": "male"}, cat)
    assert indices_module.collect_suggested_tests(computed, cat) == []

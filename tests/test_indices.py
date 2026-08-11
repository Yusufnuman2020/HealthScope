# -*- coding: utf-8 -*-
"""Klinik indeks testleri.

Bu indekslerin varlık sebebi, tek tek parametrelerin göremediği ayrımları
yapmalarıdır. Testler de tam olarak bunu sınar: De Ritis alkolik ve viral
hepatiti, Mentzer talasemi ve demir eksikliğini ayırabiliyor mu?
"""
import json
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


@pytest.fixture(scope="module")
def cases():
    with open(ROOT / "presets.json", encoding="utf-8") as handle:
        return json.load(handle)


def run(cat, values, biometrics=None):
    bio = {"yas": 45, "cinsiyet": "male", **(biometrics or {})}
    computed, unavailable = indices_module.compute(cat.indices, values, bio, cat)
    return {item["id"]: item for item in computed}, unavailable


def case_values(cases, name_fragment):
    case = next(c for c in cases if name_fragment in c["name"])
    values = {k: float(str(v).replace(",", ".")) for k, v in case["labValues"].items()}
    bio = {"yas": int(case["biometrics"]["yas"]), "cinsiyet": case["biometrics"]["cinsiyet"]}
    return values, bio


# ── Bütünlük ──────────────────────────────────────────────────────────────
def test_definitions_and_formulas_match(cat):
    assert indices_module.validate(cat.indices, set(cat.parameters)) == []


def test_every_index_nutrition_key_resolves(cat):
    for index_id, meta in cat.indices.items():
        for level, key in (meta.get("nutrition") or {}).items():
            assert cat.protocol(key) is not None, f"{index_id}.{level} -> {key}"


# ── Ayırt edicilik: indekslerin asıl varlık sebebi ────────────────────────
def test_de_ritis_separates_alcoholic_from_viral_hepatitis(cat, cases):
    """Dil modelinin yapamadığı ayrım — tek bölme işlemiyle yapılıyor."""
    alcoholic, bio_a = case_values(cases, "Alkolik Hepatit & Hepatosteatoz — Orta")
    viral, bio_v = case_values(cases, "Akut Viral Hepatit — Orta")

    a = run(cat, alcoholic, bio_a)[0]["de_ritis"]
    v = run(cat, viral, bio_v)[0]["de_ritis"]

    assert a["value"] > 2.0, "alkolik vakada AST/ALT > 2 olmalı"
    assert v["value"] < 1.0, "viral vakada AST/ALT < 1 olmalı"
    assert "alkolik" in a["interpretation"].lower()
    assert "viral" in v["interpretation"].lower()


def test_mentzer_separates_thalassemia_from_iron_deficiency(cat, cases):
    thal, bio_t = case_values(cases, "Talasemi Taşıyıcılığı — Orta")
    iron, bio_i = case_values(cases, "Demir Eksikliği Anemisi — Orta")

    t = run(cat, thal, bio_t)[0]["mentzer"]
    i = run(cat, iron, bio_i)[0]["mentzer"]

    assert t["value"] < 13.0, "talasemide Mentzer < 13 olmalı"
    assert i["value"] > 13.0, "demir eksikliğinde Mentzer > 13 olmalı"
    assert "talasemi" in t["interpretation"].lower()
    assert "demir eksikliği" in i["interpretation"].lower()


def test_homa_ir_detects_insulin_resistance(cat, cases):
    values, bio = case_values(cases, "Metabolik Sendrom & İnsülin Direnci — Orta")
    homa = run(cat, values, bio)[0]["homa_ir"]
    assert homa["value"] > 4.5
    assert homa["level"] == "high"
    assert homa["nutrition_key"] == "insulin_resistance"


def test_egfr_stages_kidney_disease(cat, cases):
    values, bio = case_values(cases, "Kronik Böbrek Hastalığı (İleri Evre) — Orta")
    egfr = run(cat, values, bio)[0]["egfr"]
    assert egfr["value"] < 30
    assert egfr["level"] == "critical"


def test_bun_creatinine_flags_prerenal_azotemia(cat, cases):
    dehydrated, bio_d = case_values(cases, "Dehidratasyon & Prerenal Azotemi — Orta")
    renal, bio_r = case_values(cases, "Kronik Böbrek Hastalığı (İleri Evre) — Orta")

    d = run(cat, dehydrated, bio_d)[0]["bun_kreatinin"]
    r = run(cat, renal, bio_r)[0]["bun_kreatinin"]
    assert d["value"] > 20, "dehidratasyonda BUN/Kr > 20 (prerenal)"
    assert d["value"] > r["value"], "prerenal oran, intrensek renalden yüksek olmalı"


def test_transferrin_saturation_separates_deficiency_from_overload(cat, cases):
    deficiency, bio_d = case_values(cases, "Demir Eksikliği Anemisi — Orta")
    overload, bio_o = case_values(cases, "Hemokromatoz (Demir Yüklenmesi) — Orta")

    d = run(cat, deficiency, bio_d)[0]["transferrin_sat"]
    o = run(cat, overload, bio_o)[0]["transferrin_sat"]
    assert d["value"] < 16
    assert o["value"] > 45
    assert o["level"] == "critical"


# ── Uygulanabilirlik kapısı ───────────────────────────────────────────────
def test_mentzer_is_skipped_without_microcytosis(cat, cases):
    """Mikrositoz yoksa Mentzer yanıltıcı olur; hiç hesaplanmamalı."""
    healthy, bio = case_values(cases, "Sağlıklı Kontrol — Genç Erkek")
    computed, _ = run(cat, healthy, bio)
    assert "mentzer" not in computed


def test_de_ritis_is_skipped_when_ast_normal(cat, cases):
    healthy, bio = case_values(cases, "Sağlıklı Kontrol — Genç Erkek")
    computed, _ = run(cat, healthy, bio)
    assert "de_ritis" not in computed


@pytest.mark.parametrize("control", [
    "Sağlıklı Kontrol — Genç Erkek",
    "Sağlıklı Kontrol — Genç Kadın",
    "Sağlıklı Kontrol — İleri Yaş",
])
def test_healthy_controls_flag_no_index(cat, cases, control):
    """Negatif kontrol: sağlıklı hastada hiçbir indeks dikkat çekmemeli."""
    values, bio = case_values(cases, control)
    computed, _ = run(cat, values, bio)
    flagged = [i["label"] for i in computed.values() if i["level"] != "normal"]
    assert flagged == [], f"sağlıklı kontrolde işaretlenen indeks: {flagged}"


# ── Eksik girdi ───────────────────────────────────────────────────────────
def test_missing_inputs_are_reported_not_silently_dropped(cat):
    computed, unavailable = run(cat, {"ast": 185.0})  # ALT yok
    missing_ids = {item["id"] for item in unavailable}
    assert "de_ritis" in missing_ids
    assert any("alt" in item["missing"] for item in unavailable)
    assert "de_ritis" not in computed


def test_zero_denominator_does_not_crash(cat):
    computed, unavailable = run(cat, {"ast": 100.0, "alt": 0.0})
    assert "de_ritis" not in computed
    assert any(item["id"] == "de_ritis" for item in unavailable)


def test_integer_indices_have_no_decimal_noise(cat, cases):
    values, bio = case_values(cases, "Sağlıklı Kontrol — Genç Erkek")
    computed, _ = run(cat, values, bio)
    assert isinstance(computed["egfr"]["value"], int)
    assert isinstance(computed["non_hdl"]["value"], int)

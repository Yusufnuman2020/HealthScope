# -*- coding: utf-8 -*-
"""Hibrit katmanın klinik özet üretimi.

Bu modülün dil modelinden bağımsız olması kasıtlıdır: özet metni model
olmadan test edilebilir, böylece prompt kalitesi ağır bir model yüklemeden
doğrulanabilir.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import clinical_brief  # noqa: E402


BASE = {
    "biometrics": {"yas": 22, "cinsiyet": "male"},
    "metrics": {"bmi": 27.5, "bmr": 1889, "status": "Pre-Obezite (Metabolik Yük)"},
    "history": "Protein tozu kullanımı",
    "genetics": "Bilinmiyor",
    "allergies": [],
    "abnormal_findings": [
        {
            "label": "AST (SGOT)", "value": 368, "unit": "U/L", "reference": "1.0-35.0",
            "status": "Yüksek", "deviation_percentage": 951.4, "domain": "Hepatoloji",
        },
        {
            "label": "ALT (SGPT)", "value": 115, "unit": "U/L", "reference": "1.0-35.0",
            "status": "Yüksek", "deviation_percentage": 228.6, "domain": "Hepatoloji",
        },
    ],
    "clinical_indices": [
        {
            "label": "De Ritis Oranı", "value": 3.2, "unit": "", "level": "borderline",
            "interpretation": "AST/ALT > 2 ancak GGT normal — kas kaynaklı artış düşünülmelidir.",
            "overridden_interpretation": "AST/ALT > 2: alkolik karaciğer hastalığı paterni ile uyumlu.",
        },
    ],
    "suggested_tests": [{"label": "CK (Kreatin Kinaz)", "reason": "De Ritis Oranı"}],
    "primary_domain": "Hepatoloji",
    "evaluated_count": 33,
}


def build(**overrides):
    return clinical_brief.build(**{**BASE, **overrides})


def test_brief_contains_patient_context():
    text = build()
    assert "22 yaşında erkek" in text
    assert "Protein tozu kullanımı" in text
    assert "Pre-Obezite" in text


def test_brief_lists_findings_with_reference_and_deviation():
    text = build()
    assert "AST (SGOT): 368 U/L" in text
    assert "referans 1.0-35.0" in text
    assert "%951.4 yüksek" in text


def test_brief_surfaces_index_interpretation():
    text = build()
    assert "De Ritis Oranı = 3.2" in text
    assert "kas kaynaklı artış" in text


def test_brief_states_which_interpretation_was_overridden():
    """Model, elenen hipotezi de görmeli — yanlış yöne sapmasın diye."""
    text = build()
    assert "bağlam olmadan şöyle yorumlanırdı" in text
    assert "alkolik karaciğer" in text


def test_brief_includes_suggested_tests():
    text = build()
    assert "EKSİK TESTLER" in text
    assert "CK (Kreatin Kinaz)" in text


def test_brief_handles_completely_normal_patient():
    text = build(abnormal_findings=[], clinical_indices=[], suggested_tests=[])
    assert "Yok; girilen 33 parametrenin tamamı" in text
    assert "EKSİK TESTLER" not in text


def test_brief_truncates_long_finding_lists():
    many = [
        {
            "label": f"Parametre {i}", "value": i, "unit": "U/L", "reference": "1-10",
            "status": "Yüksek", "deviation_percentage": float(i), "domain": "Test",
        }
        for i in range(30)
    ]
    text = build(abnormal_findings=many)
    assert "ve 18 parametre daha" in text
    assert text.count("- Parametre") == clinical_brief.MAX_FINDINGS


def test_brief_reports_allergies():
    assert "bilinen alerji yok" in build()
    assert "Yumurta, Ceviz" in build(allergies=["Yumurta", "Ceviz"])


@pytest.mark.parametrize("sex,expected", [("male", "erkek"), ("female", "kadın"), ("Erkek", "erkek")])
def test_brief_normalises_sex(sex, expected):
    text = build(biometrics={"yas": 40, "cinsiyet": sex})
    assert f"40 yaşında {expected}" in text


def test_system_prompt_forbids_inventing_values():
    """Halüsinasyon yüzeyini daraltan kurallar prompt'ta olmalı.

    Büyük/küçük harfe bağlı değil: prompt metni ölçüm sonuçlarına göre
    yeniden yazılabilir, korunması gereken şey kuralların varlığı.
    """
    prompt = clinical_brief.SYSTEM_PROMPT.lower()
    assert "uydurma" in prompt
    assert "kesin teşhis koyma" in prompt
    assert "teşhis değildir" in prompt


def test_system_prompt_blocks_drug_advice():
    """Ölçümde model 'antibiyotik tercihi' önerdi; bu açıkça yasaklanmalı.

    Not: Türkçe 'İ' harfi Python'da `.lower()` ile birleştirici noktalı bir
    karaktere dönüşür ve 'i' ile eşleşmez; bu yüzden metin ham hâliyle aranır.
    """
    prompt = clinical_brief.SYSTEM_PROMPT
    assert "doz" in prompt
    assert "tedavi önerme" in prompt


def test_system_prompt_separates_index_families():
    """Model De Ritis/FIB-4'ü inflamasyon indeksi sanıyordu; ayrım prompt'ta."""
    prompt = clinical_brief.SYSTEM_PROMPT
    assert "De Ritis" in prompt and "NLR" in prompt

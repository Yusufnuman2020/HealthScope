# -*- coding: utf-8 -*-
"""Gerçek bir hastane raporuyla ortaya çıkan hataların regresyon testleri.

Kaynak: Bolu İzzet Baysal Devlet Hastanesi, 06.08.2026, 22 yaş erkek.
Uygulama bu raporda 6 parametreyi referans dışı işaretlemişti; hastanenin
kendi referanslarına göre yalnızca 2'si gerçekten dışıydı.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import catalog as catalog_module  # noqa: E402
import config  # noqa: E402


@pytest.fixture(scope="module")
def cat():
    return catalog_module.load(config.DATABASE_PATH)


# ── A) Yapay alt sınırlar kaldırıldı ──────────────────────────────────────
@pytest.mark.parametrize("parameter_id", ["baso", "baso_perc", "eos", "eos_perc", "mono"])
def test_differential_counts_allow_zero(cat, parameter_id):
    """Hastane bu parametrelerde alt sınırı 0 kabul eder.

    Önceden alt sınır yapay olarak 0'dan yukarı çekilmişti (baso 0.01) ve
    tamamen normal bir `baso = 0.0` "düşük" işaretleniyordu.
    """
    param = cat.get(parameter_id)
    assert param.ref_min == 0.0, f"{parameter_id} alt sınırı 0 olmalı"
    assert param.is_abnormal(0.0) is False, f"{parameter_id}=0 normal sayılmalı"


def test_zero_floor_does_not_break_deviation_math(cat):
    """Alt sınır 0 iken sapma hesabı hâlâ sıfıra bölmeden çalışmalı."""
    param = cat.get("baso")
    assert param.deviation_percentage(param.ref_max + 0.5) > 0


# ── B) Cinsiyete özgü referans aralıkları ─────────────────────────────────
def test_male_creatinine_upper_limit_matches_hospital(cat):
    """Gerçek vaka: 1.12 mg/dL erkekte normal, ama tek aralıkta 'yüksek' çıkıyordu."""
    param = cat.get("kreatinin")
    assert param.is_abnormal(1.12, "male") is False
    assert param.is_abnormal(1.12, "female") is True


@pytest.mark.parametrize(
    "parameter_id", ["kreatinin", "hgb", "hct", "rbc", "ferritin", "demir", "urik_asit"]
)
def test_sex_specific_ranges_are_defined(cat, parameter_id):
    param = cat.get(parameter_id)
    assert param.ref_male is not None, f"{parameter_id} için erkek aralığı yok"
    assert param.ref_female is not None, f"{parameter_id} için kadın aralığı yok"
    assert param.range_for("male") != param.range_for("female")


def test_unknown_sex_falls_back_to_general_range(cat):
    param = cat.get("kreatinin")
    assert param.range_for(None) == (param.ref_min, param.ref_max)
    assert param.range_for("") == (param.ref_min, param.ref_max)


def test_widest_range_covers_both_sexes(cat):
    param = cat.get("hgb")
    low, high = param.widest_range()
    for sex in ("male", "female"):
        sex_low, sex_high = param.range_for(sex)
        assert low <= sex_low and high >= sex_high


def test_deviation_uses_sex_specific_bound(cat):
    """Sapma yüzdesi de cinsiyete göre hesaplanmalı."""
    param = cat.get("hgb")
    value = 12.5  # erkekte düşük, kadında normal
    assert param.is_abnormal(value, "male") is True
    assert param.is_abnormal(value, "female") is False
    assert param.deviation_percentage(value, "male") > 0


# ── C) OCR şüpheli okuma tespiti ──────────────────────────────────────────
def test_detects_lost_decimal_point(cat):
    """Gerçek vaka: EasyOCR '2.9' değerini '29' okudu ve %314 sahte sapma üretti."""
    suspects = cat.detect_suspicious({"eos_perc": "29"})
    assert len(suspects) == 1
    assert suspects[0]["parameter"] == "eos_perc"
    assert suspects[0]["reason"] == "decimal_shift"
    assert suspects[0]["suggestion"] == "2.9"


def test_detects_extra_decimal_point(cat):
    """Ters yön: '140' yerine '14.0' okunması."""
    suspects = cat.detect_suspicious({"sodyum": "14"})
    assert suspects and suspects[0]["reason"] == "decimal_shift"
    assert suspects[0]["suggestion"] == "140"


def test_normal_values_are_not_suspicious(cat):
    """Gerçek raporun doğru okunan değerleri hiç uyarı üretmemeli."""
    clean = {
        "hgb": "16.1", "hct": "46.8", "wbc": "8.8", "plt": "238", "glukoz": "77",
        "kreatinin": "1.12", "sodyum": "141", "potasyum": "4.46", "tsh": "1.040",
        "alt": "34", "ast": "24", "crp": "3.18", "baso": "0.0", "eos_perc": "2.9",
    }
    assert cat.detect_suspicious(clean) == []


def test_genuinely_abnormal_value_is_not_flagged_as_decimal_error(cat):
    """Gerçek bir patolojik değer 'ondalık hatası' sayılmamalı.

    ALT 1150 (akut viral hepatit) — 115.0 da aralık dışı olduğu için
    ondalık kayması kuralı tetiklenmez; yalnızca aşırı sapma uyarısı verilir.
    """
    suspects = cat.detect_suspicious({"alt": "1150"})
    assert len(suspects) == 1
    assert suspects[0]["reason"] == "extreme_deviation"


def test_suspicion_uses_widest_range_when_sex_unknown(cat):
    """Yükleme anında cinsiyet bilinmez; yalnızca her iki cinsiyette de
    anormal olan değerler şüpheli sayılmalı."""
    # 12.5 g/dL erkekte düşük ama kadında normal -> şüpheli sayılmamalı
    assert cat.detect_suspicious({"hgb": "12.5"}) == []

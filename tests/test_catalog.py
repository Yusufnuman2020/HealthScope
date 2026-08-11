# -*- coding: utf-8 -*-
"""Katalog bütünlüğü testleri.

Bu dosyadaki testler, projenin geçmişinde gerçekten yaşanan hata sınıfını
yakalar: form alanı / OCR anahtarı / referans aralığı / beslenme protokolü
anahtarlarının birbirini tutmaması (ör. `insülin` vs `insulin`,
`kolesterol` vs `total_kolesterol`, `b12_low` vs `vit_b12_low`).
"""
import json
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


@pytest.fixture(scope="module")
def raw_db():
    with open(config.DATABASE_PATH, encoding="utf-8") as handle:
        return json.load(handle)


def test_catalog_is_internally_consistent(cat):
    assert cat.validate() == []


def test_every_parameter_has_a_reference_range(cat):
    """Eskiden ~30 parametre referans aralığı olmadığı için sessizce atlanıyordu."""
    for param in cat.parameters.values():
        assert param.ref_min < param.ref_max, param.id


def test_every_nutrition_key_resolves_to_a_real_protocol(cat):
    for param in cat.parameters.values():
        for direction, key in param.nutrition.items():
            assert cat.protocol(key) is not None, f"{param.id}.{direction} -> {key}"


def test_no_orphan_nutrition_protocols(cat):
    """Hiçbir parametreye bağlanmayan protokol = ölü kod."""
    referenced = {k for p in cat.parameters.values() for k in p.nutrition.values()}
    assert set(cat.nutrition) - referenced == set()


def test_symptom_protocols_are_separate_and_have_triggers(cat):
    """Semptom protokolleri parametre tabanlı değil; db_key ile asla eşleşemezler."""
    assert cat.symptom_nutrition, "semptom protokolleri boş"
    for key, entry in cat.symptom_nutrition.items():
        assert entry.get("triggers"), f"{key} için tetikleyici kelime yok"
        assert key not in cat.nutrition, f"{key} iki veritabanında birden"


def test_protocol_entries_have_all_required_fields(cat):
    required = ("compounds", "foods", "synergy", "inhibitors")
    for name, protocol in {**cat.nutrition, **cat.symptom_nutrition}.items():
        for field in required:
            assert protocol.get(field), f"{name}.{field} eksik"


@pytest.mark.parametrize(
    "parameter_id",
    ["insulin", "total_kolesterol", "vit_b12", "kreatinin", "urik_asit", "crp", "vit_d"],
)
def test_historically_broken_parameters_now_resolve(cat, parameter_id):
    """Bu parametreler eskiden anahtar uyuşmazlığı yüzünden hiç analiz edilmiyordu."""
    param = cat.get(parameter_id)
    assert param is not None, f"{parameter_id} katalogda yok"
    assert param.nutrition, f"{parameter_id} için beslenme protokolü bağlanmamış"


def test_group_metadata_covers_every_parameter(cat, raw_db):
    groups = set(raw_db["PARAMETER_GROUPS"])
    assert {p.group for p in cat.parameters.values()} <= groups

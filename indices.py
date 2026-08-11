# -*- coding: utf-8 -*-
"""Klinik indeks hesaplayıcıları.

Tek tek parametrelere bakmak yerine, literatürde yeri olan formüllerle
parametreleri birleştirir. Örneğin AST ve ALT ayrı ayrı "yüksek" der; oranları
(De Ritis) ise alkolik ve viral hepatiti BİRBİRİNDEN AYIRIR — dil modelinin
başaramadığı bir ayrım.

Tasarım: eşikler, etiketler, kaynakça ve yorum metinleri `database.json`
içindeki CLINICAL_INDICES bölümündedir (tek doğruluk kaynağı, frontend de aynı
yerden okur). Formüllerin kendisi burada, kod içinde durur — JSON'dan formül
`eval` etmek hem güvensiz hem test edilemez olurdu.

Yeni indeks eklemek: JSON'a metadata kaydı + buraya aynı `id` ile bir fonksiyon.
`validate()` ikisinin eşleştiğini garanti eder.
"""
from __future__ import annotations

import math
from typing import Any, Callable

#: id -> (değerler, biyometri) -> hesaplanan değer
FORMULAS: dict[str, Callable[[dict[str, float], dict[str, Any]], float]] = {}


def formula(index_id: str):
    def register(func):
        FORMULAS[index_id] = func
        return func

    return register


# ── Endokrinoloji ─────────────────────────────────────────────────────────
@formula("homa_ir")
def _homa_ir(v, _bio):
    return v["glukoz"] * v["insulin"] / 405.0


# ── Hepatoloji ────────────────────────────────────────────────────────────
@formula("de_ritis")
def _de_ritis(v, _bio):
    return v["ast"] / v["alt"]


@formula("fib4")
def _fib4(v, bio):
    return (bio["yas"] * v["ast"]) / (v["plt"] * math.sqrt(v["alt"]))


# ── Hematoloji ────────────────────────────────────────────────────────────
@formula("mentzer")
def _mentzer(v, _bio):
    return v["mcv"] / v["rbc"]


@formula("transferrin_sat")
def _transferrin_sat(v, _bio):
    return v["demir"] / v["tibc"] * 100.0


# ── Nefroloji ─────────────────────────────────────────────────────────────
@formula("egfr")
def _egfr(v, bio):
    """CKD-EPI 2021 (ırk katsayısı içermeyen güncel sürüm)."""
    female = str(bio["cinsiyet"]).lower() in ("female", "kadın", "kadin")
    kappa = 0.7 if female else 0.9
    alpha = -0.241 if female else -0.302
    ratio = v["kreatinin"] / kappa
    result = 142.0 * (min(ratio, 1.0) ** alpha) * (max(ratio, 1.0) ** -1.200) * (0.9938 ** bio["yas"])
    return result * 1.012 if female else result


@formula("bun_kreatinin")
def _bun_kreatinin(v, _bio):
    """Üre (mg/dL) → BUN dönüşümü: BUN = Üre × 0.467 (azot payı)."""
    return (v["ure"] * 0.467) / v["kreatinin"]


# ── Elektrolit ────────────────────────────────────────────────────────────
@formula("ca_p_product")
def _ca_p_product(v, _bio):
    return v["kalsiyum"] * v["fosfor"]


@formula("osmolarite")
def _osmolarite(v, _bio):
    """Hesaplanan ozmolarite; üre mg/dL olduğu için önce BUN'a çevrilir."""
    return 2 * v["sodyum"] + v["glukoz"] / 18.0 + (v["ure"] * 0.467) / 2.8


# ── İmmünoloji ────────────────────────────────────────────────────────────
@formula("nlr")
def _nlr(v, _bio):
    return v["neu"] / v["lym"]


@formula("plr")
def _plr(v, _bio):
    return v["plt"] / v["lym"]


# ── Kardiyovasküler ───────────────────────────────────────────────────────
@formula("tg_hdl")
def _tg_hdl(v, _bio):
    return v["trigliserid"] / v["hdl"]


@formula("non_hdl")
def _non_hdl(v, _bio):
    return v["total_kolesterol"] - v["hdl"]


# ── Elektrolit ────────────────────────────────────────────────────────────
@formula("duzeltilmis_kalsiyum")
def _duzeltilmis_kalsiyum(v, _bio):
    """Payne formülü.

    Kalsiyumun yaklaşık %40'ı albümine bağlıdır; albümin düştüğünde ölçülen
    total kalsiyum düşük görünür ama iyonize (etkin) kalsiyum normal olabilir.
    Albümin g/L cinsindendir (referans orta değer 40 g/L).
    """
    return v["kalsiyum"] + 0.02 * (40.0 - v["albumin"])


# ── Gastroenteroloji ──────────────────────────────────────────────────────
@formula("lipaz_amilaz")
def _lipaz_amilaz(v, _bio):
    return v["lipaz"] / v["amilaz"]


# ── Hepatoloji ────────────────────────────────────────────────────────────
@formula("de_ritis_bilirubin")
def _kolestaz_paterni(v, _bio):
    """ALP ve GGT'nin üst sınıra göre kaç kat aştığının çarpımı.

    Tek bir enzimin yüksekliği spesifik değildir; ALP ve GGT'nin BİRLİKTE
    yükselmesi kolestaz için çok daha ayırt edicidir. Bilirubin eşlik ediyorsa
    tablo güçlenir.
    """
    alp_ratio = v["alp"] / 115.0   # yaygın ALP üst sınırı
    ggt_ratio = v["ggt"] / 55.0    # yaygın GGT üst sınırı
    return alp_ratio * ggt_ratio


# ── Değerlendirme ─────────────────────────────────────────────────────────
def condition_met(
    condition: dict[str, Any],
    values: dict[str, float],
    biometrics: dict[str, Any],
    catalog: Any,
) -> bool:
    """Tek bir koşulu değerlendirir.

    İki biçim desteklenir:
      {"parameter": "ggt", "state": "normal"}      -> laboratuvar durumu
      {"biometric": "yas", "min": 35}              -> hasta özelliği
    """
    if "parameter" in condition:
        param = catalog.get(condition["parameter"]) if catalog else None
        value = values.get(condition["parameter"])
        if param is None or value is None:
            return False
        sex = biometrics.get("cinsiyet")
        state = condition.get("state", "abnormal")
        if state == "normal":
            return not param.is_abnormal(value, sex)
        if state == "abnormal":
            return param.is_abnormal(value, sex)
        if state == "high":
            return param.is_high(value, sex)
        if state == "low":
            return param.is_abnormal(value, sex) and not param.is_high(value, sex)
        return False

    if "biometric" in condition:
        value = biometrics.get(condition["biometric"])
        if value is None:
            return False
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return str(value).lower() == str(condition.get("equals", "")).lower()
        if "min" in condition and numeric < float(condition["min"]):
            return False
        if "max" in condition and numeric > float(condition["max"]):
            return False
        return True

    return False


def is_applicable(
    meta: dict[str, Any], values: dict[str, float], catalog: Any, biometrics: dict[str, Any]
) -> bool:
    """Bazı indeksler yalnızca belirli bir tablo varken klinik anlam taşır.

    Örnek: Mentzer indeksi talasemi ile demir eksikliğini ayırır ama bu ayrım
    yalnızca MİKROSİTOZ varken anlamlıdır. Normal bir hastada hesaplanırsa
    "demir eksikliği lehine" gibi yanıltıcı bir yorum üretir.
    """
    conditions = meta.get("applicable_when") or []
    return all(condition_met(c, values, biometrics, catalog) for c in conditions)


def classify(value: float, bands: list[dict[str, Any]]) -> dict[str, Any]:
    """Değeri, artan sırada tanımlı bantlardan uygun olanına yerleştirir."""
    for band in bands:
        limit = band.get("max")
        if limit is None or value <= float(limit):
            return band
    return bands[-1]


def compute(
    definitions: dict[str, dict[str, Any]],
    values: dict[str, float],
    biometrics: dict[str, Any],
    catalog: Any = None,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Hesaplanabilen indeksleri döner.

    Girdisi eksik olan indeksler sessizce atlanmaz; hangi parametrenin eksik
    olduğu ikinci listede raporlanır — kullanıcı "neden çıkmadı" diye sormasın.
    """
    computed: list[dict[str, Any]] = []
    unavailable: list[dict[str, str]] = []

    for index_id, meta in definitions.items():
        func = FORMULAS.get(index_id)
        if func is None:
            continue

        missing = [key for key in meta["requires"] if key not in values]
        if missing:
            unavailable.append({"id": index_id, "label": meta["label"], "missing": ", ".join(missing)})
            continue

        if catalog is not None and not is_applicable(meta, values, catalog, biometrics):
            continue

        try:
            raw = func({key: values[key] for key in meta["requires"]}, biometrics)
        except (ZeroDivisionError, ValueError, KeyError):
            unavailable.append({"id": index_id, "label": meta["label"], "missing": "hesaplanamadı"})
            continue

        if not math.isfinite(raw):
            unavailable.append({"id": index_id, "label": meta["label"], "missing": "hesaplanamadı"})
            continue

        decimals = int(meta.get("decimals", 2))
        # decimals=0 ise tam sayı döndürülür; JSON'da 104.0 yerine 104 görünür.
        value = round(raw, decimals) if decimals else int(round(raw))
        band = classify(value, meta["bands"])

        level = band["level"]
        interpretation = band["text"]
        caveat: str | None = None
        tests = list((meta.get("suggest_tests") or {}).get(level, []))

        # BAĞLAM DÜZELTİCİLERİ — bir indeksin anlamı diğer parametrelere bağlıdır.
        # Gerçek vaka: De Ritis 3.2 tek başına "alkolik karaciğer" der; ama GGT
        # normalse alkol olası değildir, kas kaynaklı AST artışı düşünülmelidir.
        # İlk eşleşen düzeltici uygulanır.
        for modifier in meta.get("modifiers") or []:
            # `when_level` verilmişse düzeltici yalnızca o bantlarda çalışır.
            # Geçerlilik uyarıları (ör. "FIB-4 genç hastada güvenilmez") ancak
            # indeks zaten bir şey işaretliyorsa anlamlıdır; normal sonucu
            # gereksiz yere şüpheli hâle getirmemeli.
            allowed_levels = modifier.get("when_level")
            if allowed_levels and level not in allowed_levels:
                continue
            if all(condition_met(c, values, biometrics, catalog) for c in modifier.get("when", [])):
                level = modifier.get("level", level)
                if modifier.get("text"):
                    caveat = interpretation
                    interpretation = modifier["text"]
                tests.extend(modifier.get("suggest_tests", []))
                break

        computed.append({
            "id": index_id,
            "label": meta["label"],
            "full_name": meta["full_name"],
            "domain": meta["domain"],
            "value": value,
            "unit": meta.get("unit", ""),
            "level": level,
            "interpretation": interpretation,
            #: Düzeltici uygulandıysa, bastırılan ham yorum şeffaflık için korunur.
            "overridden_interpretation": caveat,
            "suggested_tests": list(dict.fromkeys(tests)),
            "formula": meta["formula_text"],
            "reference": meta["reference"],
            "inputs": {key: values[key] for key in meta["requires"]},
            "nutrition_key": (meta.get("nutrition") or {}).get(level),
        })

    #: Klinik olarak dikkat çekenler önce gösterilir.
    order = {"critical": 0, "high": 1, "borderline": 2, "normal": 3}
    computed.sort(key=lambda item: (order.get(item["level"], 9), item["label"]))
    return computed, unavailable


def collect_suggested_tests(computed: list[dict[str, Any]], catalog: Any) -> list[dict[str, str]]:
    """İndekslerin önerdiği ayırt edici testleri tekilleştirip etiketler.

    Katalogda karşılığı olan testler tam adıyla, olmayanlar (ör. sistatin C)
    yazıldığı gibi döner.
    """
    seen: dict[str, dict[str, str]] = {}
    for item in computed:
        for test in item.get("suggested_tests", []):
            if test in seen:
                seen[test]["reason"] += f", {item['label']}"
                continue
            param = catalog.get(test) if catalog else None
            seen[test] = {
                "id": test,
                "label": param.label if param else test,
                "in_catalog": bool(param),
                "reason": item["label"],
            }
    return list(seen.values())


def validate(definitions: dict[str, dict[str, Any]], parameter_ids: set[str]) -> list[str]:
    """JSON metadata ile kod arasındaki tutarsızlıkları döner."""
    problems: list[str] = []

    for index_id, meta in definitions.items():
        if index_id not in FORMULAS:
            problems.append(f"{index_id}: JSON'da tanımlı ama formülü yok")
            continue
        for key in meta["requires"]:
            if key not in parameter_ids:
                problems.append(f"{index_id}: '{key}' parametresi katalogda yok")
        bands = meta.get("bands") or []
        if not bands:
            problems.append(f"{index_id}: bant tanımı yok")
            continue
        if bands[-1].get("max") is not None:
            problems.append(f"{index_id}: son bant açık uçlu olmalı (max: null)")
        limits = [b["max"] for b in bands[:-1]]
        if any(limit is None for limit in limits):
            problems.append(f"{index_id}: yalnızca son bant açık uçlu olabilir")
        elif limits != sorted(limits):
            problems.append(f"{index_id}: bantlar artan sırada olmalı")

        known_levels = {b["level"] for b in bands} | {
            m["level"] for m in (meta.get("modifiers") or []) if m.get("level")
        }
        for level in (meta.get("suggest_tests") or {}):
            if level not in known_levels:
                problems.append(f"{index_id}.suggest_tests: '{level}' diye bir seviye yok")

        for position, modifier in enumerate(meta.get("modifiers") or []):
            if not modifier.get("when"):
                problems.append(f"{index_id}.modifiers[{position}]: 'when' koşulu boş")
            for condition in modifier.get("when", []):
                if "parameter" in condition and condition["parameter"] not in parameter_ids:
                    problems.append(
                        f"{index_id}.modifiers[{position}]: "
                        f"'{condition['parameter']}' parametresi katalogda yok"
                    )
                elif "parameter" not in condition and "biometric" not in condition:
                    problems.append(
                        f"{index_id}.modifiers[{position}]: koşul 'parameter' ya da 'biometric' içermeli"
                    )
            if not modifier.get("text") and not modifier.get("level"):
                problems.append(f"{index_id}.modifiers[{position}]: ne metin ne seviye değiştiriyor")

        for condition in meta.get("applicable_when") or []:
            if "parameter" in condition and condition["parameter"] not in parameter_ids:
                problems.append(f"{index_id}.applicable_when: '{condition['parameter']}' katalogda yok")

    for index_id in FORMULAS:
        if index_id not in definitions:
            problems.append(f"{index_id}: formülü var ama JSON tanımı yok")

    return problems

# -*- coding: utf-8 -*-
"""Parametre kataloğu — tek doğruluk kaynağı (single source of truth).

`database.json` içindeki PARAMETER_CATALOG bölümü; referans aralıklarını,
OCR desenlerini ve beslenme protokolü anahtarlarını TEK yerde tutar.
Backend bu modülden, frontend ise aynı JSON'u import ederek okur.
Bu sayede "form alanı var ama referans aralığı yok" ya da
"besin protokolü var ama anahtar tutmuyor" sınıfı hatalar imkânsızlaşır.
"""
from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("HealthScopeEngine.catalog")


@dataclass(frozen=True)
class Parameter:
    """Tek bir laboratuvar parametresinin eksiksiz tanımı."""

    id: str
    label: str
    short: str
    unit: str
    domain: str
    group: str
    order: int
    ref_min: float
    ref_max: float
    ocr_patterns: tuple[str, ...] = ()
    nutrition: dict[str, str] = field(default_factory=dict)
    #: Cinsiyete özgü aralıklar. Tanımlıysa `range_for` bunları önceler.
    #: Kreatinin, hemoglobin, ferritin gibi parametrelerde fizyolojik fark
    #: gerçektir; tek aralık kullanmak yanlış alarm üretir.
    ref_male: tuple[float, float] | None = None
    ref_female: tuple[float, float] | None = None

    #: Cinsiyet değeri erkek kabul edilen ifadeler.
    MALE_TOKENS = ("male", "erkek", "m", "e")

    def range_for(self, sex: str | None = None) -> tuple[float, float]:
        """Hastanın cinsiyetine uyan referans aralığını döner.

        Cinsiyet bilinmiyorsa ya da o cinsiyet için özel aralık tanımlı
        değilse genel aralığa düşülür.
        """
        if sex:
            is_male = str(sex).strip().lower() in self.MALE_TOKENS
            specific = self.ref_male if is_male else self.ref_female
            if specific is not None:
                return specific
        return (self.ref_min, self.ref_max)

    def widest_range(self) -> tuple[float, float]:
        """Tanımlı tüm aralıkları kapsayan en geniş aralık.

        Cinsiyetin bilinmediği durumlarda (ör. OCR yükleme anında) kullanılır;
        böylece yalnızca her iki cinsiyette de anormal olan değerler işaretlenir.
        """
        lows = [self.ref_min]
        highs = [self.ref_max]
        for specific in (self.ref_male, self.ref_female):
            if specific is not None:
                lows.append(specific[0])
                highs.append(specific[1])
        return (min(lows), max(highs))

    def is_abnormal(self, value: float, sex: str | None = None) -> bool:
        low, high = self.range_for(sex)
        return value < low or value > high

    def is_high(self, value: float, sex: str | None = None) -> bool:
        return value > self.range_for(sex)[1]

    def deviation_percentage(self, value: float, sex: str | None = None) -> float:
        """Referans sınırına göre sapma yüzdesi.

        Sınır sıfır olabildiği için (ör. LDL ve bazofil min = 0) payda olarak
        önce sınırın mutlak değeri, o sıfırsa referans aralığının genişliği
        kullanılır. Böylece ZeroDivisionError oluşmaz.
        """
        low, high = self.range_for(sex)
        if value > high:
            limit, delta = high, value - high
        else:
            limit, delta = low, low - value

        denominator = abs(limit) or (high - low) or 1.0
        return round(delta / denominator * 100, 1)

    def reference_text(self, sex: str | None = None) -> str:
        low, high = self.range_for(sex)
        return f"{low}-{high}"

    def nutrition_key(self, is_high: bool) -> str | None:
        return self.nutrition.get("high" if is_high else "low")


class Catalog:
    """Yüklenmiş klinik veritabanı."""

    def __init__(self, data: dict[str, Any]):
        self.groups: dict[str, dict[str, str]] = data.get("PARAMETER_GROUPS", {})
        self.clinical_dictionary: dict[str, str] = data.get("CLINICAL_DICTIONARY", {})
        self.extended_dict: dict[str, str] = data.get("extended_dict", {})
        self.nutrition: dict[str, dict[str, Any]] = data.get("BIO_NUTRITION_DB", {})
        self.symptom_nutrition: dict[str, dict[str, Any]] = data.get("SYMPTOM_NUTRITION_DB", {})
        #: Klinik indeks tanımları (eşikler, yorumlar, kaynakça).
        #: Formülleri `indices.py` içinde, aynı kimliklerle durur.
        self.indices: dict[str, dict[str, Any]] = data.get("CLINICAL_INDICES", {})

        def optional_range(meta: dict[str, Any], key: str) -> tuple[float, float] | None:
            block = meta.get(key)
            return (float(block["min"]), float(block["max"])) if block else None

        self.parameters: dict[str, Parameter] = {}
        for pid, meta in data.get("PARAMETER_CATALOG", {}).items():
            ref = meta["ref"]
            self.parameters[pid] = Parameter(
                id=pid,
                label=meta["label"],
                short=meta["short"],
                unit=meta["unit"],
                domain=meta["domain"],
                group=meta["group"],
                order=meta.get("order", 0),
                ref_min=float(ref["min"]),
                ref_max=float(ref["max"]),
                ocr_patterns=tuple(meta.get("ocr", ())),
                nutrition={k: v for k, v in (meta.get("nutrition") or {}).items() if v},
                ref_male=optional_range(meta, "ref_male"),
                ref_female=optional_range(meta, "ref_female"),
            )

        # OCR desenleri parametre başına tek regex'te birleştirilir.
        self._ocr_regexes: dict[str, re.Pattern[str]] = {}
        for pid, param in self.parameters.items():
            if not param.ocr_patterns:
                continue
            names = "|".join(param.ocr_patterns)
            # Değer aynı satırda aranır: dikey boşluk (\n) yerine sadece yatay
            # boşluk kabul edilir, aksi halde alt satırdaki alakasız sayı çekilir.
            self._ocr_regexes[pid] = re.compile(
                rf"(?:{names})[ \t\:\-\=\*\.\_\(\)HL]*(\d+(?:[.,]\d+)?)"
            )

    # ── Doğrulama ─────────────────────────────────────────────────────────
    def validate(self) -> list[str]:
        """Katalog ile beslenme veritabanı arasındaki tutarsızlıkları döner."""
        problems: list[str] = []
        for pid, param in self.parameters.items():
            if param.group not in self.groups:
                problems.append(f"{pid}: '{param.group}' grubu PARAMETER_GROUPS'ta yok")
            if param.ref_min >= param.ref_max:
                problems.append(f"{pid}: referans aralığı geçersiz ({param.ref_min}-{param.ref_max})")
            for label, specific in (("ref_male", param.ref_male), ("ref_female", param.ref_female)):
                if specific is not None and specific[0] >= specific[1]:
                    problems.append(f"{pid}.{label}: aralık geçersiz ({specific[0]}-{specific[1]})")
            for direction, key in param.nutrition.items():
                if key not in self.nutrition:
                    problems.append(f"{pid}.{direction}: '{key}' protokolü BIO_NUTRITION_DB'de yok")

        referenced = {k for p in self.parameters.values() for k in p.nutrition.values()}
        for key in sorted(set(self.nutrition) - referenced):
            problems.append(f"'{key}' protokolü hiçbir parametreye bağlı değil (ölü kayıt)")

        # Klinik indeksler: metadata ile formüller eşleşiyor mu?
        import indices as indices_module

        problems.extend(indices_module.validate(self.indices, set(self.parameters)))
        for index_id, meta in self.indices.items():
            for level, key in (meta.get("nutrition") or {}).items():
                if key not in self.nutrition:
                    problems.append(f"{index_id}.{level}: '{key}' protokolü BIO_NUTRITION_DB'de yok")

        return problems

    # ── Sorgular ──────────────────────────────────────────────────────────
    def get(self, parameter_id: str) -> Parameter | None:
        return self.parameters.get(parameter_id.lower())

    def extract_values(self, text: str) -> dict[str, str]:
        """OCR metninden katalogdaki parametreleri çıkarır."""
        found: dict[str, str] = {}
        for pid, regex in self._ocr_regexes.items():
            match = regex.search(text)
            if match:
                found[pid] = match.group(1).replace(",", ".")
        return found

    #: Bir değerin "aşırı" sayılması için sapma yüzdesi eşiği.
    EXTREME_DEVIATION_THRESHOLD = 500.0

    def detect_suspicious(self, extracted: dict[str, str]) -> list[dict[str, Any]]:
        """OCR çıktısındaki şüpheli değerleri işaretler.

        Gerçek bir hastane raporunda EasyOCR `2.9` değerini `29` olarak okudu:
        ondalık ayraç kayboldu ve tamamen normal bir eozinofil yüzdesi %314
        sapma gösteren sahte bir bulguya dönüştü. OCR'ı düzeltemeyiz ama bu
        hata sınıfını yakalayabiliriz.

        İki kural uygulanır:
          1. ONDALIK KAYMASI — değer aralık dışı ama 10'a bölünce ya da 10 ile
             çarpınca aralığa giriyorsa, ayraç hatası çok olası.
          2. AŞIRI SAPMA — sapma %500'ü aşıyorsa, doğru bile olsa kullanıcının
             gözden geçirmesi gerekir.

        Cinsiyet yükleme anında bilinmediği için EN GENİŞ aralık kullanılır;
        böylece yalnızca her iki cinsiyette de anormal olan değerler işaretlenir.
        """
        suspects: list[dict[str, Any]] = []

        for pid, raw in extracted.items():
            param = self.get(pid)
            if param is None:
                continue
            try:
                value = float(str(raw).replace(",", "."))
            except ValueError:
                continue

            low, high = param.widest_range()
            if low <= value <= high:
                continue

            inside = lambda candidate: low <= candidate <= high  # noqa: E731
            if value != 0 and inside(value / 10):
                suspects.append({
                    "parameter": pid,
                    "label": param.label,
                    "value": raw,
                    "reason": "decimal_shift",
                    "suggestion": f"{value / 10:g}",
                    "message": (
                        f"{param.label}: '{raw}' okundu. Ondalık ayraç kaybolmuş olabilir — "
                        f"'{value / 10:g}' referans aralığına ({low}-{high}) uyuyor."
                    ),
                })
                continue
            if inside(value * 10):
                suspects.append({
                    "parameter": pid,
                    "label": param.label,
                    "value": raw,
                    "reason": "decimal_shift",
                    "suggestion": f"{value * 10:g}",
                    "message": (
                        f"{param.label}: '{raw}' okundu. Fazladan ondalık ayraç olabilir — "
                        f"'{value * 10:g}' referans aralığına ({low}-{high}) uyuyor."
                    ),
                })
                continue

            deviation = param.deviation_percentage(value)
            if deviation > self.EXTREME_DEVIATION_THRESHOLD:
                suspects.append({
                    "parameter": pid,
                    "label": param.label,
                    "value": raw,
                    "reason": "extreme_deviation",
                    "suggestion": None,
                    "message": (
                        f"{param.label}: '{raw}' referans aralığından %{deviation} sapıyor. "
                        f"Doğru okunduğunu raporunuzdan teyit edin."
                    ),
                })

        return suspects

    def match_symptom_protocols(self, *free_text: str) -> list[str]:
        """Hastanın öykü metnindeki anahtar kelimelerle semptom protokollerini eşler."""
        haystack = " ".join(t for t in free_text if t).lower()
        if not haystack:
            return []
        return [
            key
            for key, entry in self.symptom_nutrition.items()
            if any(trigger in haystack for trigger in entry.get("triggers", []))
        ]

    def protocol(self, key: str) -> dict[str, Any] | None:
        return self.nutrition.get(key) or self.symptom_nutrition.get(key)

    def as_summary(self) -> dict[str, Any]:
        return {
            "parameter_count": len(self.parameters),
            "group_count": len(self.groups),
            "nutrition_protocol_count": len(self.nutrition),
            "symptom_protocol_count": len(self.symptom_nutrition),
            "clinical_index_count": len(self.indices),
            "clinical_term_count": len(self.clinical_dictionary) + len(self.extended_dict),
        }


# ── Baskın sistem hesabı ──────────────────────────────────────────────────
#: Etkilenen parametre sayısının puana katkı ağırlığı.
#: Klinik sezgi: 5 parametresi hafif bozuk bir sistem, 1 parametresi aşırı
#: bozuk bir sistemden daha güçlü kanıttır.
DOMAIN_COUNT_WEIGHT = 0.20

#: İkinci sistemin "eş baskın" sayılması için birinciye oranı.
CO_DOMINANT_RATIO = 0.85


def domain_scores(findings: list[dict[str, Any]]) -> list[tuple[str, float]]:
    """Sistem bazlı yükü hesaplar; en yüksekten düşüğe sıralı döner.

    Puanlama 118 vaka üzerinde ölçülerek seçildi:

        ham sapma yüzdesi toplamı      %80
        genişliğe göre + tavan         %76-78
        log sıkıştırma                 %81
        karekök sıkıştırma             %84
        karekök × parametre sayısı     %86  ← seçilen

    Ham yüzde neden başarısız: alt sınırı 0 olan parametreler (CRP 0-5) küçük
    mutlak sapmalarda devasa yüzde üretip tek başına tüm alanı domine ediyordu.
    Karekök aşırı değerleri sıkıştırır; sayı çarpanı ise "birden çok parametresi
    bozuk sistem" lehine ağırlık verir.
    """
    accumulated: dict[str, float] = {}
    counts: dict[str, int] = {}

    for finding in findings:
        domain = finding["domain"]
        severity = finding.get("severity")
        if severity is None:
            continue
        accumulated[domain] = accumulated.get(domain, 0.0) + math.sqrt(max(severity, 0.0))
        counts[domain] = counts.get(domain, 0) + 1

    scored = [
        (domain, value * (1 + DOMAIN_COUNT_WEIGHT * (counts[domain] - 1)))
        for domain, value in accumulated.items()
    ]
    scored.sort(key=lambda item: item[1], reverse=True)
    return scored


def co_dominant_domains(scored: list[tuple[str, float]]) -> list[str]:
    """Birinciye yakın puanlı sistemleri döner (eş baskın tablolar).

    NAFLD hem hepatik hem endokrin, hemokromatoz hem hematolojik hem hepatiktir.
    Tek bir "kazanan" dayatmak yerine yakın olanları birlikte raporlamak klinik
    olarak daha dürüsttür.
    """
    if not scored:
        return []
    top_score = scored[0][1]
    if top_score <= 0:
        return [scored[0][0]]
    return [domain for domain, value in scored if value >= top_score * CO_DOMINANT_RATIO]


def load(path: Path) -> Catalog:
    """database.json'u yükler ve tutarlılığını doğrular."""
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)

    catalog = Catalog(data)
    problems = catalog.validate()
    for problem in problems:
        logger.error("Katalog tutarsızlığı: %s", problem)
    if problems:
        raise ValueError(
            f"database.json tutarsız ({len(problems)} sorun). İlk sorun: {problems[0]}"
        )

    logger.info(
        "Katalog yüklendi: %d parametre, %d beslenme protokolü, %d semptom protokolü.",
        len(catalog.parameters),
        len(catalog.nutrition),
        len(catalog.symptom_nutrition),
    )
    return catalog


def empty() -> Catalog:
    """Veritabanı okunamadığında kullanılan boş katalog."""
    return Catalog({})

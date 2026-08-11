# -*- coding: utf-8 -*-
"""Tek seferlik migrasyon: referans aralığı düzeltmeleri.

Gerçek bir hastane raporuyla (Bolu İzzet Baysal DH, 06.08.2026) karşılaştırma
iki sınıf hata ortaya çıkardı:

A) YAPAY ALT SINIRLAR — sıfıra bölmeyi önlemek için diferansiyel sayımların
   alt sınırı 0'dan yukarı çekilmişti (baso 0.01 gibi). Hastane bu parametreler
   için alt sınırı 0 kabul ediyor; sonuç olarak tamamen normal bir `baso = 0.0`
   "düşük" işaretleniyordu. Sıfır sınırı geri veriliyor — sapma matematiği
   zaten sıfır paydaya karşı korumalı (`Parameter.deviation_percentage`).

B) CİNSİYETE ÖZGÜ ARALIK YOKLUĞU — kreatinin için tek bir aralık kullanılıyordu
   (0.66-1.09). Hastane erkekte 0.84-1.25 kullanıyor; 1.12 ölçümü bizde
   "yüksek" çıkıyordu. Klinik olarak cinsiyete bağlı olduğu iyi bilinen
   parametrelere `ref_male` / `ref_female` ekleniyor.

Kullanım:  python scripts/migrate_reference_ranges.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "database.json"

# ── A) Yapay alt sınırı kaldırılacak parametreler ─────────────────────────
#: Diferansiyel sayımlar: hastane referansı 0'dan başlar.
ZERO_FLOOR = {
    "baso": 0.0,
    "baso_perc": 0.0,
    "eos": 0.0,
    "eos_perc": 0.0,
    "mono": 0.0,
}

# ── B) Cinsiyete özgü aralıklar ───────────────────────────────────────────
#: pid -> {"male": (min, max), "female": (min, max)}
#: Kaynak: kreatinin erkek aralığı doğrudan hastane raporundan; diğerleri
#: yaygın klinik laboratuvar referanslarıdır ve hastane aralıklarından DAR
#: OLMAYACAK şekilde seçilmiştir (yanlış alarm üretmemek için).
#: C) Cihaz metodolojisine bağlı aralıklar.
#: PDW bazı analizörlerde fL, bazılarında GSD/% olarak raporlanır (hastane
#: raporunda birim "10(GSD)", referans "0-99.9" idi). Birim OCR ile ayırt
#: edilemediği için aralık yaygın raporlama biçimlerini kapsayacak şekilde
#: genişletildi; izole PDW yüksekliği tek başına klinik karar doğurmaz.
METHOD_DEPENDENT = {
    "pdw": {
        "range": (9.0, 20.0),
        "note": "Cihaza göre fL veya GSD/% olarak raporlanır; aralık geniş tutulmuştur.",
    },
}

SEX_SPECIFIC = {
    "kreatinin": {"male": (0.84, 1.25), "female": (0.66, 1.09)},
    "hgb":       {"male": (13.0, 17.5), "female": (12.0, 16.0)},
    "hct":       {"male": (39.0, 50.0), "female": (36.0, 46.0)},
    "rbc":       {"male": (4.30, 5.90), "female": (3.90, 5.20)},
    "ferritin":  {"male": (24.0, 336.0), "female": (11.0, 307.0)},
    "demir":     {"male": (65.0, 175.0), "female": (50.0, 170.0)},
    "urik_asit": {"male": (3.4, 7.0), "female": (2.4, 6.0)},
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with open(DB, encoding="utf-8") as handle:
        db = json.load(handle)

    catalog = db["PARAMETER_CATALOG"]
    changes: list[str] = []

    for pid, new_min in ZERO_FLOOR.items():
        if pid not in catalog:
            print(f"UYARI: {pid} katalogda yok, atlandı")
            continue
        old = catalog[pid]["ref"]["min"]
        if old != new_min:
            catalog[pid]["ref"]["min"] = new_min
            changes.append(f"A  {pid:12} alt sınır {old} -> {new_min}")

    for pid, spec in METHOD_DEPENDENT.items():
        if pid not in catalog:
            print(f"UYARI: {pid} katalogda yok, atlandı")
            continue
        entry = catalog[pid]
        old_min, old_max = entry["ref"]["min"], entry["ref"]["max"]
        new_min, new_max = spec["range"]
        if (old_min, old_max) != (new_min, new_max):
            entry["ref"]["min"], entry["ref"]["max"] = new_min, new_max
            entry["note"] = spec["note"]
            changes.append(f"C  {pid:12} {old_min}-{old_max} -> {new_min}-{new_max}")

    for pid, ranges in SEX_SPECIFIC.items():
        if pid not in catalog:
            print(f"UYARI: {pid} katalogda yok, atlandı")
            continue
        entry = catalog[pid]
        entry["ref_male"] = {"min": ranges["male"][0], "max": ranges["male"][1]}
        entry["ref_female"] = {"min": ranges["female"][0], "max": ranges["female"][1]}
        base = entry["ref"]
        changes.append(
            f"B  {pid:12} genel {base['min']}-{base['max']} | "
            f"erkek {ranges['male'][0]}-{ranges['male'][1]} | "
            f"kadın {ranges['female'][0]}-{ranges['female'][1]}"
        )

    print(f"{len(changes)} değişiklik:")
    for line in changes:
        print(f"  {line}")

    if args.dry_run:
        print("\n--dry-run: dosya yazılmadı")
        return 0

    with open(DB, "w", encoding="utf-8") as handle:
        json.dump(db, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(f"\n-> {DB.name} güncellendi")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

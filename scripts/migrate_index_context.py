# -*- coding: utf-8 -*-
"""Tek seferlik migrasyon: klinik indekslere bağlam ve test önerisi ekler.

Gerçek vaka (22 yaş erkek, 22.07.2026): AST 368, ALT 115, **GGT 15 (normal)**,
bilirubin ve albümin normal, kreatinin 1.41.

Uygulama De Ritis 3.2 hesaplayıp "alkolik karaciğer hastalığı paterni" dedi.
Hastayı gören hekim de aynı hipotezle alkol sorusunu sordu — ama GGT'nin normal
olduğunu görüp bunu eledi ve tabloyu protein takviyesi / kas kaynağına bağladı.

Uygulamanın eksiği hesap değil, BAĞLAM'dı. Bu migrasyon üç şey ekler:

  1) modifiers      — bir indeksin yorumunu başka parametrelere göre değiştirir
  2) suggest_tests  — belirsizliği çözecek ayırt edici testi önerir
  3) applicable_when— indeksin geçersiz olduğu popülasyonlarda susturur

Kullanım:  python scripts/migrate_index_context.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "database.json"

# ── Bağlam düzelticileri ──────────────────────────────────────────────────
MODIFIERS: dict[str, list[dict]] = {
    "de_ritis": [
        {
            # Alkole bağlı karaciğer hasarında GGT vakaların büyük çoğunluğunda
            # yükselir. GGT normalken AST/ALT>2, alkolden çok KAS kaynağını
            # düşündürür (AST iskelet kasında da bol bulunur).
            "when": [
                {"parameter": "ast", "state": "high"},
                {"parameter": "ggt", "state": "normal"},
            ],
            "level": "borderline",
            "text": (
                "AST/ALT > 2 ancak GGT normal — alkole bağlı karaciğer hasarı olası değil. "
                "AST iskelet kasında da bulunduğu için kas kaynaklı artış (yoğun egzersiz, "
                "travma, kreatin/protein takviyesi) öncelikli düşünülmelidir."
            ),
            "suggest_tests": ["ck"],
        }
    ],
    "fib4": [
        {
            # FIB-4 kronik viral hepatit ve NAFLD hastalarında, orta-ileri yaş
            # popülasyonda doğrulanmıştır. Genç hastada ve akut transaminaz
            # yüksekliğinde formülün AST terimi indeksi kendiliğinden şişirir.
            "when": [{"biometric": "yas", "max": 35}],
            # Geçerlilik uyarısı yalnızca indeks bir şey işaretlediğinde anlamlı;
            # normal FIB-4'ü gereksiz yere şüpheli göstermemeli.
            "when_level": ["borderline", "high", "critical"],
            "level": "borderline",
            "text": (
                "FIB-4 orta-ileri yaşta, kronik karaciğer hastalığı olan popülasyonda "
                "doğrulanmıştır; 35 yaş altında güvenilir değildir. Akut transaminaz "
                "yüksekliğinde formüldeki AST terimi indeksi yapay olarak yükseltir — "
                "bu sonuç fibrozis göstergesi olarak yorumlanmamalıdır."
            ),
        }
    ],
    "egfr": [
        {
            # Kreatinin kas kütlesiyle orantılıdır. Genç, kaslı erkekte ya da
            # kreatin takviyesi kullananda kreatinin temelli eGFR gerçek GFR'yi
            # sistematik olarak düşük tahmin eder.
            "when": [
                {"parameter": "kreatinin", "state": "high"},
                {"biometric": "yas", "max": 40},
            ],
            "when_level": ["borderline", "high", "critical"],
            "level": "borderline",
            "text": (
                "Kreatinin temelli eGFR, yüksek kas kütlesinde gerçek filtrasyon hızını "
                "düşük tahmin eder. Genç ve kaslı bireylerde ya da kreatin takviyesi "
                "kullananlarda bu sonuç tek başına böbrek hastalığı anlamına gelmez."
            ),
            "suggest_tests": ["sistatin C (kas kütlesinden bağımsız GFR)"],
        }
    ],
}

# ── Seviyeye bağlı test önerileri ─────────────────────────────────────────
SUGGEST_TESTS: dict[str, dict[str, list[str]]] = {
    "mentzer": {"borderline": ["hemoglobin elektroforezi"]},
    "transferrin_sat": {"critical": ["ferritin"], "high": ["ferritin"]},
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with open(DB, encoding="utf-8") as handle:
        db = json.load(handle)

    indices = db["CLINICAL_INDICES"]
    catalog = db["PARAMETER_CATALOG"]
    changes: list[str] = []

    for index_id, modifiers in MODIFIERS.items():
        if index_id not in indices:
            print(f"UYARI: {index_id} indeksi yok, atlandı")
            continue
        indices[index_id]["modifiers"] = modifiers
        changes.append(f"modifiers  {index_id:16} ({len(modifiers)} düzeltici)")

    for index_id, mapping in SUGGEST_TESTS.items():
        if index_id not in indices:
            print(f"UYARI: {index_id} indeksi yok, atlandı")
            continue
        indices[index_id]["suggest_tests"] = mapping
        changes.append(f"tests      {index_id:16} {mapping}")

    # PCT: PDW ile aynı sınıf — bu analizör trombosit indekslerini farklı
    # metodolojiyle raporluyor (referans 0-9.99).
    if "pct" in catalog:
        old = dict(catalog["pct"]["ref"])
        catalog["pct"]["ref"]["min"] = 0.10
        catalog["pct"]["ref"]["max"] = 0.60
        catalog["pct"]["note"] = "Cihaza göre farklı ölçekte raporlanır; aralık geniş tutulmuştur."
        changes.append(f"aralik     pct              {old['min']}-{old['max']} -> 0.1-0.6")

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

# -*- coding: utf-8 -*-
"""HealthScope doğruluk değerlendirmesi.

`presets.json` içindeki klinik vakaları çalıştırır ve motorun her katmanını
ayrı ayrı puanlar. Amaç, "analiz doğru mu?" sorusunu tahminle değil ölçümle
cevaplamaktır.

Üç katman ayrı ölçülür çünkü doğrulukları çok farklıdır:

  1. SAPMA TESPİTİ    — deterministik: referans aralığı karşılaştırması
  2. ALAN TESPİTİ     — deterministik: baskın organ sistemi hesabı
  3. BESLENME EŞLEŞME — deterministik: katalog anahtar çözümlemesi
  4. DİL MODELİ       — olasılıksal: BERTurk fill-mask çıkarımı

Kullanım:
    python scripts/evaluate.py                 # sunucu çalışıyor olmalı
    python scripts/evaluate.py --offline       # dil modeli olmadan, sadece 1-3
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import catalog as catalog_module  # noqa: E402
import config  # noqa: E402
import indices as indices_module  # noqa: E402

GREEN, RED, YELLOW, DIM, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[0m"


def tick(ok: bool) -> str:
    return f"{GREEN}✔{RESET}" if ok else f"{RED}✘{RESET}"


def load_cases() -> list[dict]:
    with open(ROOT / "presets.json", encoding="utf-8") as handle:
        return json.load(handle)


def call_analyze(case: dict, base_url: str) -> dict:
    payload = {
        "values": case["labValues"],
        "biometrics": {
            "yas": int(case["biometrics"]["yas"]),
            "cinsiyet": case["biometrics"]["cinsiyet"],
            "kilo": float(case["biometrics"]["kilo"]),
            "boy": float(case["biometrics"]["boy"]),
        },
        "medical": {
            "kronik": case["medical"]["kronik"] or "Yok",
            "alerjiler": case["medical"]["alerjiler"],
            "genetik_riskler": [case["medical"]["genetik"]] if case["medical"]["genetik"] else [],
        },
    }
    request = urllib.request.Request(
        f"{base_url}/analyze", json.dumps(payload).encode(), {"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def evaluate_offline(case: dict, cat: catalog_module.Catalog) -> dict:
    """Dil modeli olmadan deterministik katmanları hesaplar."""
    flagged: set[str] = set()
    domains: dict[str, float] = {}
    protocols: set[str] = set()

    sex = case["biometrics"]["cinsiyet"]
    rows = []

    for key, raw in case["labValues"].items():
        param = cat.get(key)
        if param is None:
            continue
        value = float(str(raw).replace(",", "."))
        if not param.is_abnormal(value, sex):
            continue
        flagged.add(param.id)
        low, high = param.range_for(sex)
        is_high = param.is_high(value, sex)
        distance = (value - high) if is_high else (low - value)
        width = high - low
        rows.append({"domain": param.domain, "severity": distance / width if width > 0 else distance})
        nutrition_key = param.nutrition_key(is_high)
        if nutrition_key:
            protocols.add(nutrition_key)

    # Backend ile AYNI puanlama kullanilir; olcum gercegi yansitsin.
    ranked = catalog_module.domain_scores(rows)
    domains = dict(ranked)
    # Sapma yoksa API ile ayni varsayilan kullanilir.
    top_domain = ranked[0][0] if ranked else "Genel Metabolik Durum"

    numeric = {}
    for key, raw in case["labValues"].items():
        if cat.get(key) is not None:
            numeric[key] = float(str(raw).replace(",", "."))
    computed, _ = indices_module.compute(
        cat.indices,
        numeric,
        {"yas": int(case["biometrics"]["yas"]), "cinsiyet": case["biometrics"]["cinsiyet"]},
        cat,
    )

    return {
        "flagged": flagged,
        "domain": top_domain,
        "protocols": protocols,
        "indices": computed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="HealthScope doğruluk değerlendirmesi")
    parser.add_argument("--url", default=f"http://127.0.0.1:{config.PORT}")
    parser.add_argument("--offline", action="store_true", help="Dil modeli katmanını atla")
    args = parser.parse_args()

    cat = catalog_module.load(config.DATABASE_PATH)
    cases = load_cases()

    totals = {"flag": [0, 0], "domain": [0, 0], "protocol": [0, 0], "index": [0, 0], "llm": [0, 0]}

    print(f"\n{'=' * 78}\n  HEALTHSCOPE DOĞRULUK DEĞERLENDİRMESİ — {len(cases)} klinik vaka\n{'=' * 78}")

    for case in cases:
        expected = case.get("expected")
        if not expected:
            continue

        offline = evaluate_offline(case, cat)
        print(f"\n{case['name']}")
        print(f"{DIM}  beklenen alan: {expected['primary_domain']}{RESET}")

        # 1. Sapma tespiti — beklenen parametreler işaretlendi mi?
        missed = [p for p in expected["must_flag"] if p not in offline["flagged"]]
        ok_flag = not missed
        totals["flag"][0] += len(expected["must_flag"]) - len(missed)
        totals["flag"][1] += len(expected["must_flag"])
        print(f"  {tick(ok_flag)} Sapma tespiti  : {len(expected['must_flag']) - len(missed)}/{len(expected['must_flag'])}"
              + (f"  {RED}kaçan: {', '.join(missed)}{RESET}" if missed else ""))

        # 2. Baskın alan
        ok_domain = offline["domain"] == expected["primary_domain"]
        totals["domain"][0] += int(ok_domain)
        totals["domain"][1] += 1
        print(f"  {tick(ok_domain)} Baskın alan    : {offline['domain']}"
              + ("" if ok_domain else f"  {RED}(beklenen {expected['primary_domain']}){RESET}"))

        # 3. Beslenme protokolleri
        missing_protocols = [p for p in expected["key_protocols"] if p not in offline["protocols"]]
        ok_protocol = not missing_protocols
        totals["protocol"][0] += len(expected["key_protocols"]) - len(missing_protocols)
        totals["protocol"][1] += len(expected["key_protocols"])
        print(f"  {tick(ok_protocol)} Beslenme eşleş.: "
              f"{len(expected['key_protocols']) - len(missing_protocols)}/{len(expected['key_protocols'])}"
              + (f"  {RED}eksik: {', '.join(missing_protocols)}{RESET}" if missing_protocols else ""))

        # 4. Klinik indeksler — beklenti vakaya göre değişir (bkz. index_check)
        flagged_indices = [i for i in offline["indices"] if i["level"] != "normal"]
        check = expected.get("index_check", "na")

        if check == "na":
            # Bu sistem için tanımlı indeks yok; ölçüme dahil edilmez.
            print(f"{DIM}  – Klinik indeks  : bu sistem için tanımlı indeks yok{RESET}")
        else:
            if check == "clean":
                ok_index = not flagged_indices
                detail = "temiz (beklendiği gibi)" if ok_index else (
                    f"{len(flagged_indices)} yanlış uyarı: "
                    + ", ".join(f"{i['label']}={i['value']}" for i in flagged_indices[:3])
                )
            elif check == "flagged":
                ok_index = bool(flagged_indices)
                detail = (
                    "tüm parametreler normalken riski yakaladı: "
                    + ", ".join(f"{i['label']}={i['value']}" for i in flagged_indices[:3])
                ) if ok_index else "gizli riski yakalayamadı"
            else:  # on_target
                on_target = [i for i in flagged_indices if i["domain"] == expected["primary_domain"]]
                ok_index = bool(on_target)
                detail = (
                    ", ".join(f"{i['label']}={i['value']}" for i in on_target[:3])
                    if on_target
                    else f"{len(flagged_indices)} uyarı var ama {expected['primary_domain']} alanında yok"
                )
            totals["index"][0] += int(ok_index)
            totals["index"][1] += 1
            print(f"  {tick(ok_index)} Klinik indeks  : {detail}")

        # 5. Dil modeli — üretilen teşhis vakayla konu olarak ilgili mi?
        if args.offline:
            continue
        try:
            response = call_analyze(case, args.url)
        except (urllib.error.URLError, TimeoutError) as exc:
            print(f"  {YELLOW}!{RESET} Dil modeli     : sunucuya ulaşılamadı ({exc})")
            continue

        inference = response["ai_inference_results"]
        candidates = inference["probabilities_chart_data"]
        blob = " ".join(f"{c['diagnosis']} {c['raw_token']}" for c in candidates).lower()
        relevant = [topic for topic in expected["clinical_topic"] if topic in blob]
        ok_llm = bool(relevant)
        totals["llm"][0] += int(ok_llm)
        totals["llm"][1] += 1

        top = candidates[0]
        print(f"  {tick(ok_llm)} Dil modeli     : \"{top['diagnosis'][:52]}\" "
              f"{DIM}(ham %{top['model_score']}, {inference['inference_ms']}ms){RESET}")
        if relevant:
            print(f"{DIM}      konu örtüşmesi: {', '.join(relevant)}{RESET}")
        else:
            print(f"      {RED}vakayla konu örtüşmesi YOK{RESET} {DIM}(beklenen: {', '.join(expected['clinical_topic'][:4])}...){RESET}")

    # ── Özet ──────────────────────────────────────────────────────────────
    print(f"\n{'=' * 78}\n  ÖZET\n{'=' * 78}")
    labels = {
        "flag": "Sapma tespiti      (deterministik)",
        "domain": "Baskın alan tespiti (deterministik)",
        "protocol": "Beslenme eşleşmesi  (deterministik)",
        "index": "Klinik indeks isabeti (deterministik)",
        "llm": "Dil modeli konu isabeti (olasılıksal)",
    }
    for key, label in labels.items():
        hit, total = totals[key]
        if total == 0:
            continue
        pct = hit / total * 100
        color = GREEN if pct >= 90 else (YELLOW if pct >= 60 else RED)
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        print(f"  {label:38} {color}{bar} {hit}/{total} (%{pct:.0f}){RESET}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

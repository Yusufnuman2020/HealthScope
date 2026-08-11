# -*- coding: utf-8 -*-
"""Çıkarım katmanlarını aynı vaka setinde karşılaştırır.

"Hangi yaklaşım daha iyi?" sorusunu ölçümle cevaplar. Üç aday:

    baseline   BERTurk fill-mask            (mevcut sistem)
    rules      kural motoru + klinik indeks (deterministik)
    hybrid     kural motoru -> üretken LLM  (yeni)

Ölçüt: üretilen metnin, vakanın beklenen klinik konularıyla örtüşmesi
(`presets.json` içindeki `clinical_topic`). Ölçüt cömerttir — alt dizge
araması yapar — yani sonuçlar bir ÜST SINIR olarak okunmalıdır.

Kullanım:
    python scripts/benchmark_inference.py --url http://127.0.0.1:8000
    python scripts/benchmark_inference.py --limit 20        # hızlı deneme
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config  # noqa: E402

GREEN, RED, YELLOW, DIM, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[0m"


def load_cases(limit: int | None) -> list[dict]:
    with open(ROOT / "presets.json", encoding="utf-8") as handle:
        cases = [c for c in json.load(handle) if c.get("expected", {}).get("clinical_topic")]
    return cases[:limit] if limit else cases


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
    with urllib.request.urlopen(request, timeout=300) as response:
        return json.load(response)


def topic_hit(text: str, topics: list[str]) -> list[str]:
    lowered = text.lower()
    return [topic for topic in topics if topic in lowered]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=f"http://127.0.0.1:{config.PORT}")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    cases = load_cases(args.limit)
    print(f"\n{'=' * 80}")
    print(f"  ÇIKARIM KIYASLAMASI — {len(cases)} klinik vaka")
    print(f"{'=' * 80}")

    scores = {"baseline": 0, "rules": 0, "hybrid": 0}
    counted = {"baseline": 0, "rules": 0, "hybrid": 0}
    durations = {"baseline": 0.0, "hybrid": 0.0}
    narrative_available = False

    for index, case in enumerate(cases, 1):
        topics = case["expected"]["clinical_topic"]
        try:
            started = time.time()
            payload = call_analyze(case, args.url)
            total_ms = (time.time() - started) * 1000
        except (urllib.error.URLError, TimeoutError) as exc:
            print(f"{RED}  sunucuya ulaşılamadı: {exc}{RESET}")
            return 1

        # 1) BERTurk fill-mask
        diagnoses = payload["ai_inference_results"]["probabilities_chart_data"]
        baseline_text = " ".join(f"{d['diagnosis']} {d['raw_token']}" for d in diagnoses)
        baseline_hits = topic_hit(baseline_text, topics)
        scores["baseline"] += bool(baseline_hits)
        counted["baseline"] += 1
        durations["baseline"] += payload["ai_inference_results"]["inference_ms"]

        # 2) Kural motoru: bulgu etiketleri + indeks yorumları
        findings = payload["clinical_findings"]["abnormal_parameters_detected"]
        indices = payload.get("clinical_indices", {}).get("computed", [])
        rules_text = " ".join(
            [f["label"] + " " + f["domain"] for f in findings]
            + [i["label"] + " " + i["interpretation"] for i in indices]
            + [payload["clinical_findings"]["primary_focus_domain"]]
        )
        rules_hits = topic_hit(rules_text, topics)
        scores["rules"] += bool(rules_hits)
        counted["rules"] += 1

        # 3) Hibrit üretken katman
        narrative = payload.get("narrative")
        hybrid_hits: list[str] = []
        if narrative and narrative.get("text"):
            narrative_available = True
            hybrid_hits = topic_hit(narrative["text"], topics)
            scores["hybrid"] += bool(hybrid_hits)
            counted["hybrid"] += 1
            durations["hybrid"] += narrative.get("elapsed_ms", 0.0)

        mark = lambda hits: f"{GREEN}✔{RESET}" if hits else f"{RED}✘{RESET}"  # noqa: E731
        line = (
            f"  {index:>3}. {mark(baseline_hits)} baseline  {mark(rules_hits)} rules  "
            + (f"{mark(hybrid_hits)} hybrid  " if narrative_available else "")
            + f"{DIM}{case['name'][:44]}{RESET}"
        )
        print(line)
        if args.verbose and narrative and narrative.get("text"):
            print(f"{DIM}       {narrative['text'][:160]}...{RESET}")

    # ── Özet ──────────────────────────────────────────────────────────────
    print(f"\n{'=' * 80}\n  SONUÇ\n{'=' * 80}")
    labels = {
        "baseline": "BERTurk fill-mask      (mevcut)",
        "rules": "Kural motoru + indeks  (deterministik)",
        "hybrid": "Hibrit: kural -> LLM   (yeni)",
    }
    for key, label in labels.items():
        total = counted[key]
        if total == 0:
            print(f"  {label:40} {DIM}çalıştırılmadı{RESET}")
            continue
        hit = scores[key]
        pct = hit / total * 100
        color = GREEN if pct >= 80 else (YELLOW if pct >= 55 else RED)
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        extra = ""
        if key in durations and durations[key]:
            extra = f"  {DIM}ort. {durations[key] / total:.0f} ms{RESET}"
        print(f"  {label:40} {color}{bar} {hit}/{total} (%{pct:.0f}){RESET}{extra}")

    if not narrative_available:
        print(
            f"\n{YELLOW}  Hibrit katman kapalı.{RESET} Etkinleştirmek için .env içinde:\n"
            "    HEALTHSCOPE_LLM_PROVIDER=local\n"
            "    HEALTHSCOPE_LLM_MODEL=Qwen/Qwen2.5-3B-Instruct"
        )
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

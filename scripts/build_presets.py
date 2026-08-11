# -*- coding: utf-8 -*-
"""Klinik vaka havuzunu (`presets.json`) üretir ve doğrular.

Yaklaşım: 100+ paneli elle yazmak yerine **klinik arketip + şiddet derecesi**.
Her arketip, hastalığın tipik "orta şiddet" panelini tanımlar. Hafif ve ağır
varyantlar, değerin *referans sınırından sapma miktarı* ölçeklenerek üretilir:

    hafif  = sınır + (orta_sapma × 0.45)
    ağır   = sınır + (orta_sapma × 1.90)

Bu yöntem sapmanın yönünü ve klinik tutarlılığı korur; rastgele sayı üretmez.
Fizyolojik olarak imkânsız değerler `PHYSIO_LIMITS` ile kırpılır.

Her vaka, normal bir temel panelin üzerine yazılır — yani paneller gerçek bir
tahlil raporu gibi eksiksizdir, "sadece anormaller girilmiş" yapaylığı olmaz.

Yazmadan önce her vaka katalogla doğrulanır:
  * bilinmeyen parametre kimliği var mı,
  * vakayı tanımlayan değerler gerçekten referans dışı mı,
  * negatif kontroller gerçekten temiz mi.

`must_flag` ve `key_protocols` vaka verisinden TÜRETİLİR (veri girişi hatasını
yakalar). Buna karşılık `primary_domain` ve `clinical_topic` ELLE belirlenir —
onlar motorun sınandığı bağımsız klinik ölçütlerdir.

Kullanım:
    python scripts/build_presets.py            # presets.json'u yeniden üretir
    python scripts/build_presets.py --check    # sadece doğrular, yazmaz
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import catalog as catalog_module  # noqa: E402
import config  # noqa: E402

# ── Cinsiyete göre normal temel panel ─────────────────────────────────────
BASE_MALE: dict[str, str] = {
    "wbc": "7.0", "rbc": "4.90", "hgb": "14.8", "hct": "44.0", "mcv": "89.0", "mch": "30.2",
    "mchc": "33.5", "plt": "250", "rdw": "13.0", "pdw": "12.5", "pct": "0.25", "mpv": "9.5",
    "neu_perc": "55", "neu": "4.0", "lym_perc": "33", "lym": "2.2", "mono_perc": "7", "mono": "0.5",
    "eos_perc": "2", "eos": "0.15", "baso_perc": "0.6", "baso": "0.04",
    "ure": "30", "kreatinin": "0.90", "ast": "22", "alt": "24", "ggt": "25", "alp": "70",
    "ck": "95", "urik_asit": "4.8", "sodyum": "140", "potasyum": "4.2", "fosfor": "3.4",
    "kalsiyum": "9.5",
    "tsh": "2.0", "ft4": "0.90", "ft3": "3.2", "parathormon": "45", "ferritin": "120",
    "vit_b12": "400", "folat": "9.0", "vit_d": "38",
    "crp": "2.0", "sedim": "8",
    "glukoz": "88", "hba1c": "5.2", "insulin": "8", "yassi_epitel": "2", "yassi_olmayan_epitel": "0",
    "total_kolesterol": "175", "ldl": "105", "hdl": "52", "trigliserid": "110",
    "demir": "90", "tibc": "300",
    # Gerçek Türk laboratuvar panellerinde standart olan parametreler
    "albumin": "44.0", "total_bilirubin": "0.70", "direkt_bilirubin": "0.15",
    "amilaz": "55", "lipaz": "30",
}

BASE_FEMALE: dict[str, str] = {
    **BASE_MALE,
    "rbc": "4.40", "hgb": "13.2", "hct": "39.5", "kreatinin": "0.75", "urik_asit": "3.9",
    "ferritin": "60", "demir": "80",
}

#: Şiddet ölçeklemesinden sonra uygulanan fizyolojik güvenlik sınırları.
#: (yaşamla bağdaşmayan değerler üretilmesin)
PHYSIO_LIMITS: dict[str, tuple[float, float]] = {
    "hgb": (3.0, 24.0), "hct": (10.0, 68.0), "rbc": (1.2, 8.5), "plt": (3, 1200),
    "wbc": (0.3, 180.0), "neu": (0.05, 160.0), "lym": (0.1, 120.0),
    "potasyum": (1.8, 8.5), "sodyum": (105, 178), "kalsiyum": (5.0, 17.0), "fosfor": (0.6, 12.0),
    "glukoz": (25, 900), "hba1c": (3.2, 17.0), "insulin": (0.5, 300),
    "kreatinin": (0.2, 16.0), "ure": (5, 300), "urik_asit": (0.5, 22.0),
    "tsh": (0.005, 150.0), "ft4": (0.05, 8.0), "ft3": (0.4, 25.0),
    "ferritin": (1, 6000), "vit_b12": (30, 3000), "vit_d": (2, 160), "folat": (0.3, 60),
    "ck": (10, 90000), "ast": (3, 5000), "alt": (3, 5000), "ggt": (3, 3000), "alp": (10, 2000),
    "crp": (0.1, 500), "sedim": (1, 140), "parathormon": (2, 900),
    "total_kolesterol": (60, 700), "ldl": (15, 550), "hdl": (10, 140), "trigliserid": (20, 2000),
    "demir": (3, 400), "tibc": (90, 600), "mcv": (50, 135), "mch": (12, 45),
    "albumin": (12.0, 60.0), "total_bilirubin": (0.1, 40.0), "direkt_bilirubin": (0.02, 30.0),
    "amilaz": (5, 4000), "lipaz": (3, 8000),
}

SEVERITIES = (("Hafif", 0.45), ("Orta", 1.00), ("Ağır", 1.90))


# ── Klinik arketipler ─────────────────────────────────────────────────────
# labs   : ORTA şiddetteki tipik panel (sadece hastalığa özgü parametreler)
# people : şiddet varyantı başına demografi — (cinsiyet, yaş, boy, kilo)
# domain : motorun bulması BEKLENEN baskın sistem (bağımsız klinik ölçüt)
# topics : dil modeli çıktısında geçmesi beklenen kelimeler (bağımsız ölçüt)
ARCHETYPES: list[dict] = [
    # ═══ HEPATOLOJİ ═══════════════════════════════════════════════════════
    {
        "name": "Alkolik Hepatit & Hepatosteatoz",
        "icon": "🍺",
        "description": "AST baskın transaminaz artışı, GGT yüksekliği ve makrositoz.",
        "domain": "Hepatoloji",
        "topics": ["karaciğer", "yağlanma", "hepatit", "siroz", "alkol", "enzim"],
        "history": "Alkol kullanım bozukluğu",
        "people": [("male", 38, 180, 88), ("male", 45, 182, 95), ("male", 54, 176, 91)],
        "labs": {"ast": "185", "alt": "92", "ggt": "285", "alp": "195", "mcv": "102.4",
                 "plt": "115", "trigliserid": "380", "hdl": "28", "folat": "2.8",
                 "vit_d": "14", "crp": "18", "ferritin": "550"},
    },
    {
        "name": "Akut Viral Hepatit",
        "icon": "🦠",
        "description": "ALT baskın masif transaminaz yüksekliği; hepatoselüler hasar paterni.",
        "domain": "Hepatoloji",
        "topics": ["karaciğer", "hepatit", "enzim", "viral", "sarılık", "bilirubin"],
        "history": "İki haftadır halsizlik, bulantı ve idrar renginde koyulaşma",
        "people": [("male", 22, 176, 68), ("male", 27, 178, 70), ("female", 33, 165, 60)],
        "labs": {"ast": "820", "alt": "1150", "ggt": "180", "alp": "165",
                 "wbc": "3.6", "lym_perc": "48", "plt": "132", "crp": "12", "sedim": "28"},
    },
    {
        "name": "Kolestaz & Safra Yolu Tıkanıklığı",
        "icon": "🟡",
        "description": "ALP ve GGT baskın kolestatik patern; transaminazlar görece korunmuş.",
        "domain": "Hepatoloji",
        "topics": ["safra", "karaciğer", "kolestatik", "sarılık", "bilirubin", "enzim"],
        "history": "Sağ üst kadran ağrısı ve yaygın kaşıntı",
        "people": [("female", 51, 162, 72), ("female", 62, 160, 78), ("male", 68, 172, 80)],
        "labs": {"alp": "480", "ggt": "620", "ast": "88", "alt": "95",
                 "total_kolesterol": "310", "ldl": "210", "crp": "24", "sedim": "42", "wbc": "12.2"},
    },
    {
        "name": "Non-Alkolik Yağlı Karaciğer (NAFLD)",
        "icon": "🫒",
        "description": "ALT baskın hafif enzim artışı, insülin direnci ve dislipidemi birlikteliği.",
        "domain": "Hepatoloji",
        "topics": ["karaciğer", "yağlanma", "enzim", "obezite", "insülin", "metabolizma"],
        "history": "Obezite, hareketsiz yaşam; alkol kullanmıyor",
        "people": [("male", 41, 174, 96), ("male", 49, 178, 104), ("female", 56, 161, 92)],
        "labs": {"alt": "78", "ast": "52", "ggt": "88", "trigliserid": "295", "hdl": "33",
                 "insulin": "31", "glukoz": "116", "hba1c": "6.1", "urik_asit": "7.6", "ferritin": "410"},
    },

    # ═══ HEMATOLOJİ ═══════════════════════════════════════════════════════
    {
        "name": "Megaloblastik Anemi (B12 Eksikliği)",
        "icon": "🥦",
        "description": "Makrositer anemi, pansitopeni eğilimi ve nörolojik risk.",
        "domain": "Hematoloji",
        "topics": ["anemi", "b12", "folat", "kan", "hemoglobin", "eritrosit", "kobalamin"],
        "history": "Atrofik gastrit, uyuşma ve kronik yorgunluk",
        "people": [("female", 57, 166, 62), ("female", 68, 168, 55), ("male", 74, 170, 63)],
        "labs": {"hgb": "8.8", "rbc": "2.80", "hct": "26.5", "mcv": "112.5", "mch": "36.5",
                 "rdw": "19.5", "plt": "125", "wbc": "3.8", "neu": "1.7",
                 "vit_b12": "85", "folat": "2.1", "vit_d": "18", "sedim": "28"},
    },
    {
        "name": "Demir Eksikliği Anemisi",
        "icon": "🩸",
        "description": "Mikrositer hipokrom anemi; düşük ferritin, yüksek demir bağlama kapasitesi.",
        "domain": "Hematoloji",
        "topics": ["anemi", "demir", "ferritin", "kan", "hemoglobin", "eritrosit", "emilim"],
        "history": "Menoraji ve halsizlik",
        "people": [("female", 27, 168, 60), ("female", 34, 165, 58), ("female", 46, 160, 63)],
        "labs": {"hgb": "8.9", "hct": "28.5", "mcv": "68.5", "mch": "21.5", "mchc": "31.0",
                 "rdw": "18.8", "plt": "455", "ferritin": "4", "demir": "18", "tibc": "445",
                 "vit_d": "22"},
    },
    {
        "name": "Folat Eksikliği Anemisi",
        "icon": "🥬",
        "description": "Folat yetersizliğine bağlı makrositoz; metilasyon döngüsü bozukluğu.",
        "domain": "Hematoloji",
        "topics": ["anemi", "folat", "kan", "hemoglobin", "eritrosit", "beslenme", "vitamin"],
        "history": "Dengesiz beslenme, uzun süreli alkol kullanımı",
        "people": [("male", 36, 175, 66), ("female", 44, 163, 57), ("male", 59, 171, 69)],
        "labs": {"folat": "1.6", "hgb": "10.2", "mcv": "108.0", "mch": "35.0", "rdw": "17.5",
                 "plt": "142", "vit_b12": "260", "vit_d": "20"},
    },
    {
        "name": "Talasemi Taşıyıcılığı",
        "icon": "🧬",
        "description": "Mikrositoz var ama demir depoları normal — demir eksikliğinden ayırıcı tanı.",
        "domain": "Hematoloji",
        "topics": ["anemi", "eritrosit", "kan", "hemoglobin", "genetik", "mikrositer"],
        "history": "Ailede Akdeniz anemisi öyküsü",
        "genetics": "Ailede talasemi taşıyıcılığı",
        "people": [("male", 19, 174, 66), ("male", 24, 176, 72), ("female", 31, 162, 55)],
        "labs": {"rbc": "6.10", "hgb": "11.2", "hct": "35.0", "mcv": "62.0", "mch": "19.5",
                 "rdw": "14.6"},
    },
    {
        "name": "Polisitemi (Eritrositoz)",
        "icon": "🫀",
        "description": "Artmış eritrosit kitlesi, hiperviskozite ve tromboz riski.",
        "domain": "Hematoloji",
        "topics": ["eritrosit", "kan", "hemoglobin", "pıhtı", "koagülasyon", "trombosit"],
        "history": "Sigara kullanımı ve uyku apnesi",
        "people": [("male", 47, 176, 84), ("male", 55, 174, 88), ("male", 63, 170, 86)],
        "labs": {"rbc": "6.80", "hgb": "19.5", "hct": "58.0", "plt": "520", "pct": "0.48",
                 "wbc": "12.5", "urik_asit": "8.2", "ferritin": "18", "demir": "42"},
    },
    {
        "name": "Pansitopeni (Kemik İliği Baskılanması)",
        "icon": "🦴",
        "description": "Üç seride birden azalma; enfeksiyon ve kanama riski yüksek.",
        "domain": "Hematoloji",
        "topics": ["kan", "kemik", "lökosit", "trombosit", "anemi", "enfeksiyon", "eritrosit"],
        "history": "Kemoterapi sonrası kontrol",
        "people": [("male", 52, 172, 68), ("male", 61, 170, 64), ("female", 69, 158, 56)],
        "labs": {"wbc": "1.8", "neu": "0.6", "lym": "0.8", "rbc": "2.90", "hgb": "9.2",
                 "hct": "28.0", "plt": "38", "pct": "0.04", "pdw": "18.5",
                 "ferritin": "780", "crp": "42", "sedim": "58"},
    },
    {
        "name": "Hemokromatoz (Demir Yüklenmesi)",
        "icon": "🧲",
        "description": "Yüksek ferritin ve transferrin satürasyonu; doku demir birikimi.",
        "domain": "Hematoloji",
        "topics": ["demir", "ferritin", "karaciğer", "eklem", "diyabet", "kan"],
        "history": "Eklem ağrıları ve cilt renginde koyulaşma",
        "genetics": "Ailede herediter hemokromatoz",
        "people": [("male", 42, 178, 80), ("male", 48, 180, 84), ("male", 57, 175, 82)],
        "labs": {"ferritin": "1850", "demir": "245", "tibc": "230", "ast": "78", "alt": "92",
                 "ggt": "110", "glukoz": "138", "hba1c": "6.8"},
    },
    {
        "name": "Reaktif Trombositoz",
        "icon": "🩹",
        "description": "İnflamasyon ve demir eksikliğine ikincil trombosit artışı.",
        "domain": "Hematoloji",
        "topics": ["trombosit", "kan", "pıhtı", "koagülasyon", "demir", "iltihap"],
        "history": "Kronik inflamatuar bağırsak hastalığı",
        "people": [("female", 29, 164, 54), ("male", 37, 177, 71), ("female", 50, 161, 66)],
        "labs": {"plt": "780", "pct": "0.62", "pdw": "17.8", "ferritin": "6", "demir": "22",
                 "tibc": "430", "hgb": "10.6", "mcv": "72.0", "crp": "28", "sedim": "46"},
    },
    {
        "name": "Trombositopeni (İmmün)",
        "icon": "💜",
        "description": "İzole trombosit düşüklüğü; peteşi ve kanama eğilimi.",
        "domain": "Hematoloji",
        "topics": ["trombosit", "kan", "kanama", "bağışıklık", "immün", "otoimmün"],
        "history": "Ciltte morarma ve diş eti kanaması",
        "people": [("female", 25, 167, 58), ("female", 39, 163, 64), ("male", 48, 174, 78)],
        "labs": {"plt": "28", "pct": "0.03", "pdw": "19.2", "mpv": "12.4"},
    },

    # ═══ İMMÜNOLOJİ ═══════════════════════════════════════════════════════
    {
        "name": "Akut Bakteriyel Enfeksiyon",
        "icon": "🦠",
        "description": "Lökositoz, nötrofili ve yüksek CRP ile akut inflamatuar yanıt.",
        "domain": "İmmünoloji",
        "topics": ["enfeksiyon", "iltihap", "bakteri", "lökosit", "nötrofil", "ateş", "zatürre"],
        "history": "Ateş ve öksürük; pnömoni şüphesi",
        "people": [("male", 31, 178, 80), ("male", 40, 180, 85), ("female", 58, 160, 70)],
        "labs": {"wbc": "18.5", "neu": "15.7", "neu_perc": "85", "lym_perc": "8", "plt": "385",
                 "crp": "185", "sedim": "78", "ferritin": "480", "glukoz": "145",
                 "ure": "48", "kreatinin": "1.25", "sodyum": "135", "demir": "45"},
    },
    {
        "name": "Sepsis & Çoklu Organ Yükü",
        "icon": "🔥",
        "description": "Ağır sistemik inflamatuar yanıt; renal ve hematolojik tutulum eşlik ediyor.",
        "domain": "İmmünoloji",
        "topics": ["enfeksiyon", "sepsis", "bakteri", "iltihap", "lökosit", "böbrek", "nötrofil"],
        "history": "Ürosepsis şüphesi, yüksek ateş ve konfüzyon",
        "people": [("male", 59, 172, 74), ("female", 72, 158, 60), ("male", 81, 168, 62)],
        "labs": {"wbc": "26.5", "neu": "24.4", "neu_perc": "92", "lym_perc": "5", "plt": "84",
                 "pct": "0.09", "crp": "320", "sedim": "105", "ure": "128", "kreatinin": "3.10",
                 "potasyum": "5.6", "sodyum": "131", "hgb": "9.8", "ferritin": "1250",
                 "glukoz": "195"},
    },
    {
        "name": "Alerjik / Paraziter Eozinofili",
        "icon": "🌿",
        "description": "Belirgin eozinofil artışı; atopi veya parazitoz düşündüren tablo.",
        "domain": "İmmünoloji",
        "topics": ["alerji", "eozinofil", "astım", "bağışıklık", "immün", "parazit"],
        "history": "Alerjik astım ve mevsimsel şikayetler",
        "allergies": ["Polen", "Fındık"],
        "people": [("male", 19, 177, 66), ("female", 28, 166, 58), ("male", 44, 175, 79)],
        "labs": {"wbc": "11.8", "eos_perc": "22", "eos": "2.60", "baso_perc": "2.8",
                 "baso": "0.14", "vit_d": "24"},
    },
    {
        "name": "Lenfositoz (Viral / Lenfoproliferatif)",
        "icon": "🧫",
        "description": "Belirgin lenfosit artışı; viral veya lenfoproliferatif süreç ayrımı gerekir.",
        "domain": "İmmünoloji",
        "topics": ["lenfosit", "kan", "bağışıklık", "immün", "lösemi", "lenfoma", "viral"],
        "history": "Boyunda şişlik ve gece terlemesi",
        "people": [("male", 34, 176, 74), ("male", 66, 172, 76), ("female", 71, 159, 61)],
        "labs": {"wbc": "42.0", "lym": "37.0", "lym_perc": "88", "neu_perc": "9",
                 "hgb": "10.5", "plt": "118", "sedim": "48", "urik_asit": "9.2"},
    },
    {
        "name": "Nötropeni (Enfeksiyon Riski)",
        "icon": "🛡️",
        "description": "Nötrofil sayısında kritik düşüş; fırsatçı enfeksiyon riski.",
        "domain": "İmmünoloji",
        "topics": ["nötrofil", "lökosit", "enfeksiyon", "bağışıklık", "immün", "kan"],
        "history": "Tekrarlayan ağız içi enfeksiyonları",
        "people": [("female", 32, 165, 57), ("male", 45, 173, 70), ("female", 60, 158, 63)],
        "labs": {"wbc": "2.4", "neu": "0.5", "neu_perc": "21", "lym_perc": "68", "vit_b12": "138"},
    },
    {
        "name": "Kronik İnflamatuar / Romatolojik Aktivite",
        "icon": "🌡️",
        "description": "Süregelen akut faz yanıtı, kronik hastalık anemisi ve yüksek sedimantasyon.",
        "domain": "İmmünoloji",
        "topics": ["iltihap", "romatizma", "eklem", "otoimmün", "immün", "artrit", "anemi"],
        "history": "Romatoid artrit tanısı, sabah tutukluğu",
        "people": [("female", 43, 162, 65), ("female", 55, 160, 68), ("male", 64, 171, 77)],
        "labs": {"crp": "62", "sedim": "88", "plt": "540", "hgb": "10.4", "mcv": "80.0",
                 "ferritin": "460", "demir": "28", "tibc": "210", "alp": "128", "vit_d": "15"},
    },

    # ═══ ENDOKRİNOLOJİ ════════════════════════════════════════════════════
    {
        "name": "Hipertiroidi (Graves)",
        "icon": "🏃",
        "description": "Hipermetabolik süreç, baskılanmış TSH ve kardiyak taşikardi eşlikli klinik.",
        "domain": "Endokrinoloji",
        "topics": ["tiroid", "hipertiroidi", "guatr", "metabolizma", "t3", "t4", "tsh", "çarpıntı"],
        "history": "Çarpıntı, kilo kaybı ve anksiyete",
        "genetics": "Ailede tiroid hastalıkları",
        "people": [("female", 24, 168, 52), ("female", 31, 165, 48), ("male", 46, 177, 66)],
        "labs": {"tsh": "0.02", "ft4": "2.45", "ft3": "6.8", "total_kolesterol": "145",
                 "ldl": "85", "alp": "115", "ferritin": "65", "vit_d": "26", "ast": "38"},
    },
    {
        "name": "Hipotiroidi (Hashimoto)",
        "icon": "🐢",
        "description": "Yavaşlamış metabolizma, dislipidemi ve hafif anemi eşlikli tablo.",
        "domain": "Endokrinoloji",
        "topics": ["tiroid", "hipotiroidi", "metabolizma", "tsh", "kilo", "guatr", "t4"],
        "history": "Kilo alma, üşüme ve kabızlık",
        "people": [("female", 36, 164, 76), ("female", 44, 162, 82), ("female", 58, 158, 79)],
        "labs": {"tsh": "28.4", "ft4": "0.38", "ft3": "1.9", "total_kolesterol": "285",
                 "ldl": "195", "hdl": "38", "trigliserid": "225", "hgb": "11.4",
                 "mcv": "94.0", "ck": "310", "sodyum": "134", "vit_d": "16", "ferritin": "22"},
    },
    {
        "name": "Tip 2 Diyabet (Yeni Tanı)",
        "icon": "🍬",
        "description": "Belirgin hiperglisemi, yüksek HbA1c ve eşlik eden dislipidemi.",
        "domain": "Endokrinoloji",
        "topics": ["diyabet", "şeker", "glukoz", "insülin", "metabolizma", "hba1c", "direnç"],
        "history": "Poliüri ve polidipsi",
        "genetics": "Ailede diyabet öyküsü",
        "people": [("male", 44, 175, 92), ("male", 53, 173, 96), ("female", 61, 159, 88)],
        "labs": {"glukoz": "212", "hba1c": "9.4", "insulin": "26", "total_kolesterol": "255",
                 "ldl": "170", "hdl": "33", "trigliserid": "340", "urik_asit": "7.4",
                 "alt": "58", "ggt": "72", "kreatinin": "1.15", "vit_d": "19"},
    },
    {
        "name": "Metabolik Sendrom & İnsülin Direnci",
        "icon": "⚖️",
        "description": "Normoglisemik ama hiperinsülinemik; prediyabetik metabolik yük.",
        "domain": "Endokrinoloji",
        "topics": ["insülin", "direnç", "metabolizma", "obezite", "şeker", "diyabet"],
        "history": "Polikistik over sendromu ve kilo artışı",
        "people": [("female", 29, 166, 84), ("female", 38, 163, 91), ("male", 47, 176, 103)],
        "labs": {"insulin": "38", "glukoz": "104", "hba1c": "5.9", "trigliserid": "285",
                 "hdl": "34", "total_kolesterol": "228", "ldl": "148", "alt": "52",
                 "ggt": "58", "urik_asit": "6.4", "crp": "8.5", "vit_d": "17"},
    },
    {
        "name": "Reaktif Hipoglisemi",
        "icon": "📉",
        "description": "Açlık glukozu referansın altında; nöroglikopenik semptom riski.",
        "domain": "Endokrinoloji",
        "topics": ["hipoglisemi", "şeker", "glukoz", "insülin", "metabolizma", "titreme"],
        "history": "Öğün atlama sonrası baş dönmesi ve titreme",
        "people": [("female", 21, 170, 54), ("female", 26, 168, 52), ("male", 35, 178, 68)],
        "labs": {"glukoz": "48", "insulin": "2.1", "hba1c": "4.4", "vit_d": "21", "ferritin": "14"},
    },
    {
        "name": "Ağır D Vitamini Eksikliği & Osteomalazi",
        "icon": "☀️",
        "description": "Sekonder hiperparatiroidi ile seyreden ciddi D vitamini yetersizliği.",
        "domain": "Endokrinoloji",
        "topics": ["vitamin", "kemik", "kalsiyum", "osteoporoz", "fosfor", "paratiroid"],
        "history": "Yaygın kemik ağrısı ve kas güçsüzlüğü",
        "people": [("female", 33, 162, 64), ("female", 41, 160, 68), ("male", 66, 170, 71)],
        "labs": {"vit_d": "6", "parathormon": "168", "kalsiyum": "8.1", "fosfor": "2.2",
                 "alp": "215", "ck": "180", "ferritin": "18", "hgb": "11.8"},
    },
    {
        "name": "Primer Hiperparatiroidi",
        "icon": "🦴",
        "description": "Kalsiyum-fosfor dengesizliği ve kemik rezorbsiyonu riski.",
        "domain": "Endokrinoloji",
        "topics": ["kalsiyum", "kemik", "osteoporoz", "taş", "fosfor", "paratiroid"],
        "history": "Tekrarlayan böbrek taşları",
        "people": [("female", 48, 168, 67), ("female", 58, 172, 70), ("male", 67, 174, 78)],
        "labs": {"kalsiyum": "11.8", "fosfor": "2.1", "parathormon": "185", "alp": "135",
                 "ure": "42", "kreatinin": "1.12", "vit_d": "16", "yassi_epitel": "4",
                 "yassi_olmayan_epitel": "2"},
    },

    # ═══ NEFROLOJİ ════════════════════════════════════════════════════════
    {
        "name": "Gut Artriti & Hiperürisemi",
        "icon": "🥩",
        "description": "Yüksek ürik asit, akut inflamasyon ve metabolik sendrom bileşenleri.",
        "domain": "Nefroloji",
        "topics": ["gut", "ürik", "eklem", "artrit", "romatizma", "böbrek", "taş"],
        "history": "Gut ve hipertansiyon",
        "genetics": "Ailede ürolitiyazis",
        "people": [("male", 43, 178, 92), ("male", 52, 175, 98), ("male", 61, 171, 94)],
        "labs": {"urik_asit": "10.4", "wbc": "12.8", "neu": "9.6", "crp": "26", "sedim": "42",
                 "ure": "45", "kreatinin": "1.15", "total_kolesterol": "255", "ldl": "175",
                 "hdl": "38", "trigliserid": "240", "glukoz": "108", "insulin": "18",
                 "plt": "340", "vit_d": "22"},
    },
    {
        "name": "Kronik Böbrek Hastalığı (İleri Evre)",
        "icon": "🫘",
        "description": "İleri renal yetmezlik; hiperkalemi, anemi ve mineral-kemik bozukluğu.",
        "domain": "Nefroloji",
        "topics": ["böbrek", "üre", "kreatinin", "potasyum", "anemi", "kemik", "fosfor"],
        "history": "Diyabetik nefropati ve hipertansiyon",
        "people": [("male", 55, 173, 78), ("male", 64, 171, 74), ("female", 73, 156, 62)],
        "labs": {"ure": "165", "kreatinin": "4.80", "potasyum": "6.2", "fosfor": "6.8",
                 "kalsiyum": "7.9", "parathormon": "310", "sodyum": "133", "hgb": "9.4",
                 "rbc": "3.20", "ferritin": "95", "urik_asit": "9.6", "crp": "14",
                 "sedim": "52", "glukoz": "158", "hba1c": "7.6", "vit_d": "12"},
    },
    {
        "name": "Akut Böbrek Hasarı",
        "icon": "⚡",
        "description": "Hızlı kreatinin yükselmesi ve elektrolit dengesizliği.",
        "domain": "Nefroloji",
        "topics": ["böbrek", "kreatinin", "üre", "potasyum", "idrar", "elektrolit"],
        "history": "Kontrast madde sonrası idrar çıkışında azalma",
        "people": [("male", 49, 176, 82), ("male", 63, 172, 79), ("female", 76, 157, 64)],
        "labs": {"kreatinin": "3.60", "ure": "142", "potasyum": "5.8", "fosfor": "5.6",
                 "kalsiyum": "8.0", "urik_asit": "9.1", "crp": "36", "wbc": "13.8",
                 "yassi_olmayan_epitel": "6"},
    },
    {
        "name": "Dehidratasyon & Prerenal Azotemi",
        "icon": "💧",
        "description": "Hemokonsantrasyon ve orantısız üre artışı; sıvı açığı tablosu.",
        "domain": "Nefroloji",
        "topics": ["böbrek", "üre", "dehidratasyon", "sodyum", "idrar", "kreatinin"],
        "history": "Üç gündür ishal ve yetersiz sıvı alımı",
        "people": [("male", 34, 178, 70), ("male", 62, 172, 66), ("male", 78, 168, 58)],
        "labs": {"ure": "96", "kreatinin": "1.35", "sodyum": "149", "potasyum": "3.2",
                 "hgb": "17.2", "hct": "51.5", "rbc": "5.90", "urik_asit": "8.6", "crp": "9"},
    },

    # ═══ ELEKTROLİT ═══════════════════════════════════════════════════════
    {
        "name": "Hiponatremi (SIADH Paterni)",
        "icon": "🧂",
        "description": "İzole ciddi sodyum düşüklüğü; nörolojik semptom riski yüksek.",
        "domain": "Elektrolit",
        "topics": ["sodyum", "elektrolit", "böbrek", "baş dönmesi", "idrar", "ödem"],
        "history": "Konfüzyon ve bulantı; diüretik kullanımı",
        "people": [("female", 54, 160, 66), ("female", 70, 157, 62), ("male", 79, 166, 65)],
        "labs": {"sodyum": "118", "potasyum": "3.3", "ure": "14", "kreatinin": "0.58",
                 "urik_asit": "2.1"},
    },
    {
        "name": "Hipokalemi (Potasyum Kaybı)",
        "icon": "🍌",
        "description": "Kas güçsüzlüğü ve aritmi riski taşıyan potasyum düşüklüğü.",
        "domain": "Elektrolit",
        "topics": ["potasyum", "elektrolit", "kas", "aritmi", "çarpıntı", "böbrek"],
        "history": "Uzun süreli diüretik kullanımı ve kusma",
        "people": [("female", 41, 163, 58), ("female", 59, 159, 64), ("male", 68, 170, 72)],
        "labs": {"potasyum": "2.6", "sodyum": "133", "kalsiyum": "8.2", "fosfor": "2.3",
                 "ck": "285", "ure": "18"},
    },
    {
        "name": "Hiperkalemi (Potasyum Yüksekliği)",
        "icon": "⚠️",
        "description": "Kardiyak iletim bozukluğu riski taşıyan akut potasyum artışı.",
        "domain": "Elektrolit",
        "topics": ["potasyum", "elektrolit", "böbrek", "aritmi", "kalp", "kas"],
        "history": "Böbrek yetmezliği ve potasyum tutucu ilaç kullanımı",
        "people": [("male", 57, 174, 80), ("male", 66, 170, 76), ("female", 74, 158, 68)],
        "labs": {"potasyum": "6.6", "kreatinin": "2.40", "ure": "98", "fosfor": "5.4",
                 "kalsiyum": "8.3", "sodyum": "134"},
    },

    # ═══ KAS-İSKELET ══════════════════════════════════════════════════════
    {
        "name": "Rabdomiyoliz (Kas Yıkımı)",
        "icon": "💪",
        "description": "Masif CK yüksekliği, elektrolit kayması ve renal risk.",
        "domain": "Kas-İskelet",
        "topics": ["kas", "böbrek", "kinaz", "hasar", "idrar", "potasyum"],
        "history": "Yoğun antrenman sonrası koyu renkli idrar",
        "people": [("male", 20, 181, 77), ("male", 23, 183, 79), ("male", 29, 179, 84)],
        "labs": {"ck": "18500", "ast": "420", "alt": "165", "ure": "52", "kreatinin": "1.65",
                 "potasyum": "5.9", "fosfor": "5.2", "kalsiyum": "8.0", "urik_asit": "8.8",
                 "crp": "22", "wbc": "13.5"},
    },

    # ═══ KARDİYOVASKÜLER ══════════════════════════════════════════════════
    {
        "name": "Ailesel Hiperkolesterolemi",
        "icon": "🫀",
        "description": "İzole ağır LDL yüksekliği; erken ateroskleroz riski.",
        "domain": "Kardiyovasküler",
        "topics": ["kolesterol", "lipid", "ldl", "damar", "ateroskleroz", "kalp"],
        "history": "Babada 45 yaşında miyokard infarktüsü",
        "genetics": "Ailede erken koroner arter hastalığı",
        "people": [("male", 28, 180, 76), ("male", 36, 179, 81), ("female", 49, 164, 70)],
        "labs": {"total_kolesterol": "385", "ldl": "290", "hdl": "38", "trigliserid": "180"},
    },
    {
        "name": "Aterojenik Dislipidemi",
        "icon": "🍔",
        "description": "Yüksek trigliserid ve düşük HDL birlikteliği; metabolik risk paterni.",
        "domain": "Kardiyovasküler",
        "topics": ["trigliserid", "kolesterol", "lipid", "hdl", "damar", "kalp", "metabolizma"],
        "history": "Hareketsiz yaşam ve yüksek karbonhidratlı beslenme",
        "people": [("male", 39, 176, 94), ("male", 48, 174, 99), ("female", 57, 161, 87)],
        "labs": {"trigliserid": "620", "hdl": "26", "total_kolesterol": "295", "ldl": "155",
                 "glukoz": "118", "insulin": "29", "hba1c": "6.2", "alt": "62", "urik_asit": "7.9"},
    },

    # ═══ GASTROENTEROLOJİ (yeni parametrelerle) ═══════════════════════════
    {
        "name": "Akut Pankreatit (Biliyer)",
        "icon": "🫄",
        "description": "Lipaz ve amilazda belirgin artış; safra taşına bağlı biliyer patern.",
        "domain": "Gastroenteroloji",
        "topics": ["pankreas", "amilaz", "lipaz", "safra", "karın ağrısı", "enzim"],
        "history": "Şiddetli karın ağrısı, bulantı; safra taşı öyküsü",
        "people": [("female", 44, 163, 78), ("female", 53, 160, 82), ("male", 61, 172, 88)],
        "labs": {"lipaz": "620", "amilaz": "480", "alp": "210", "ggt": "180",
                 "total_bilirubin": "2.8", "direkt_bilirubin": "1.9", "alt": "165",
                 "ast": "140", "crp": "95", "wbc": "16.2", "neu": "13.8", "glukoz": "148"},
    },
    {
        "name": "Alkolik Pankreatit",
        "icon": "🥃",
        "description": "Lipaz/Amilaz oranı yüksek; alkole bağlı pankreas hasarı paterni.",
        "domain": "Gastroenteroloji",
        "topics": ["pankreas", "lipaz", "alkol", "enzim", "karın ağrısı"],
        "history": "Kronik alkol kullanımı, tekrarlayan karın ağrısı",
        "people": [("male", 39, 176, 74), ("male", 47, 178, 71), ("male", 55, 174, 69)],
        "labs": {"lipaz": "890", "amilaz": "210", "ggt": "320", "ast": "125", "alt": "68",
                 "mcv": "101.5", "albumin": "32", "crp": "48", "trigliserid": "420",
                 "kalsiyum": "8.1"},
    },
    {
        "name": "Tıkanma Sarılığı (Kolestaz)",
        "icon": "🟠",
        "description": "ALP, GGT ve konjuge bilirubinde belirgin artış; safra akımı obstrüksiyonu.",
        "domain": "Hepatoloji",
        "topics": ["safra", "sarılık", "bilirubin", "kolestatik", "karaciğer", "tıkanma"],
        "history": "Ciltte sararma, koyu idrar, kaşıntı",
        "people": [("female", 58, 161, 70), ("male", 66, 173, 76), ("female", 74, 156, 63)],
        "labs": {"alp": "540", "ggt": "680", "total_bilirubin": "8.4", "direkt_bilirubin": "6.2",
                 "ast": "95", "alt": "110", "total_kolesterol": "320", "albumin": "34",
                 "crp": "32", "wbc": "13.1"},
    },
    {
        "name": "Hipoalbüminemi (Sentetik Fonksiyon Kaybı)",
        "icon": "💧",
        "description": "Düşük albümin; onkotik basınç düşüşü ve ödem riski.",
        "domain": "Hepatoloji",
        "topics": ["albümin", "karaciğer", "ödem", "protein", "beslenme", "sentez"],
        "history": "Bacaklarda şişlik, iştahsızlık",
        "people": [("male", 62, 170, 66), ("female", 71, 157, 58), ("male", 78, 168, 61)],
        "labs": {"albumin": "26", "kalsiyum": "7.9", "total_bilirubin": "1.9",
                 "ast": "78", "alt": "62", "plt": "118", "hgb": "10.4", "crp": "26",
                 "ure": "52", "kreatinin": "1.32"},
    },

    # ═══ SEMPTOM TABANLI (öykü metninden protokol tetikler) ═══════════════
    {
        "name": "Reflü & Gastrit İlişkili Demir Eksikliği",
        "icon": "🔥",
        "description": "Kronik mide şikayeti ve buna eşlik eden emilim kaynaklı demir eksikliği.",
        "domain": "Hematoloji",
        "topics": ["mide", "reflü", "gastrit", "demir", "anemi", "emilim"],
        "history": "Kronik reflü ve gastrit şikayeti, mide yanması",
        "people": [("female", 30, 167, 62), ("female", 35, 166, 64), ("male", 52, 175, 83)],
        "labs": {"ferritin": "9", "hgb": "11.5", "mcv": "76.0", "demir": "28", "tibc": "398",
                 "vit_b12": "180"},
    },
    {
        "name": "Kronik Yorgunluk & Stres Sendromu",
        "icon": "😴",
        "description": "Çoklu mikrobesin eksikliği; ağırlıklı olarak semptom protokolleri devreye girer.",
        "domain": "Hematoloji",
        "topics": ["yorgunluk", "stres", "vitamin", "demir", "anemi", "uyku", "tiroid"],
        "history": "Kronik yorgunluk, anksiyete, uykusuzluk ve kabızlık",
        "people": [("female", 24, 172, 58), ("female", 29, 170, 57), ("male", 41, 177, 73)],
        "labs": {"vit_d": "11", "ferritin": "8", "vit_b12": "142", "tsh": "5.9", "hgb": "11.9",
                 "folat": "3.2"},
    },
]

# ── Negatif kontroller (şiddet varyantı yok) ──────────────────────────────
CONTROLS: list[dict] = [
    {
        "name": "✅ Sağlıklı Kontrol — Genç Erkek",
        "description": "Negatif kontrol: hiçbir sapma bulunmamalı, protokol tetiklenmemeli.",
        "domain": "Genel Metabolik Durum", "topics": [],
        "history": "Yok, rutin check-up",
        "person": ("male", 29, 178, 74), "labs": {},
    },
    {
        "name": "✅ Sağlıklı Kontrol — Genç Kadın",
        "description": "Negatif kontrol: kadın referans aralıklarıyla tamamen normal panel.",
        "domain": "Genel Metabolik Durum", "topics": [],
        "history": "Yok, rutin check-up",
        "person": ("female", 26, 165, 58), "labs": {},
    },
    {
        "name": "✅ Sağlıklı Kontrol — İleri Yaş",
        "description": "Negatif kontrol: 71 yaşında, tüm parametreler referans aralığında.",
        "domain": "Genel Metabolik Durum", "topics": [],
        "history": "Yok, yıllık kontrol",
        "person": ("male", 71, 170, 72), "labs": {},
    },
    {
        "name": "🟢 Sınır Değerler (Referans Sınırında)",
        "description": "Negatif kontrol: değerler referans sınırına çok yakın ama içinde.",
        "domain": "Genel Metabolik Durum", "topics": [],
        "history": "Yok",
        "person": ("female", 47, 164, 66),
        "labs": {"glukoz": "98", "hba1c": "5.5", "alt": "34", "ast": "34", "kreatinin": "1.05",
                 "tsh": "5.2", "ldl": "128", "hdl": "41", "trigliserid": "148", "vit_d": "31"},
    },
]


def _decimals(text: str) -> int:
    return len(text.split(".")[1]) if "." in text else 0


def scale_value(param, moderate: str, factor: float, sex: str) -> str:
    """Referans sınırından sapmayı ölçekler; yön ve klinik tutarlılık korunur.

    Referans aralığı cinsiyete göre değişebildiği için (kreatinin, hemoglobin,
    ferritin...) ölçekleme de hastanın cinsiyetine göre yapılır.
    """
    value = float(moderate)
    digits = _decimals(moderate)
    ref_low, ref_high = param.range_for(sex)

    if value > ref_high:
        scaled = ref_high + (value - ref_high) * factor
    elif value < ref_low:
        scaled = ref_low - (ref_low - value) * factor
    else:
        return moderate  # zaten normal — şiddetle değişmez

    low, high = PHYSIO_LIMITS.get(param.id, (float("-inf"), float("inf")))
    scaled = max(low, min(high, scaled))

    result = round(scaled, digits)
    # Yuvarlama değeri referans aralığına geri sokmuş olabilir; bir basamak ittir.
    step = 10 ** -digits if digits else 1
    guard = 0
    while ref_low <= result <= ref_high and guard < 50:
        result = round(result + (step if value > ref_high else -step), digits)
        guard += 1

    return f"{result:.{digits}f}" if digits else str(int(result))


def build_case(spec: dict, cat: catalog_module.Catalog, severity: str | None,
               factor: float, person: tuple) -> dict:
    sex, age, height, weight = person
    labs = dict(BASE_MALE if sex == "male" else BASE_FEMALE)

    for key, moderate in spec["labs"].items():
        param = cat.get(key)
        if param is None:
            labs[key] = moderate  # doğrulama aşamasında hata olarak raporlanır
            continue
        labs[key] = scale_value(param, moderate, factor, sex) if severity else moderate

    icon = spec.get("icon", "")
    name = f"{icon} {spec['name']}".strip()
    if severity:
        name = f"{name} — {severity}"

    return {
        "name": name,
        "description": spec["description"],
        "biometrics": {"boy": str(height), "kilo": str(weight), "yas": str(age), "cinsiyet": sex},
        "medical": {
            "kronik": spec.get("history", "Yok"),
            "genetik": spec.get("genetics", ""),
            "alerjiler": list(spec.get("allergies", [])),
        },
        "labValues": labs,
        "expected": {
            "primary_domain": spec["domain"],
            "must_flag": [],
            "key_protocols": [],
            "clinical_topic": list(spec["topics"]),
        },
    }


def index_expectation(domain: str, is_control: bool, has_labs: bool,
                      index_domains: set[str]) -> str:
    """Klinik indeks katmanının bu vakada ne yapması beklendiğini belirler.

    clean     : hiçbir indeks uyarı vermemeli (tamamen sağlıklı hasta)
    flagged   : parametrelerin hepsi referans içinde OLMASINA RAĞMEN bir indeks
                uyarı vermeli — indekslerin varlık sebebi budur
    on_target : beklenen sistemde bir indeks uyarı vermeli
    na        : bu sistem için tanımlı indeks yok, ölçüme dahil edilmez
    """
    if is_control:
        return "flagged" if has_labs else "clean"
    return "on_target" if domain in index_domains else "na"


def derive_and_validate(case: dict, intended: dict, cat: catalog_module.Catalog,
                        is_control: bool) -> list[str]:
    """`must_flag` / `key_protocols`'u veriden türetir; tutarsızlıkları döner."""
    problems: list[str] = []

    sex = case["biometrics"]["cinsiyet"]
    flagged: list[str] = []
    protocols: list[str] = []
    for key, raw in case["labValues"].items():
        param = cat.get(key)
        if param is None:
            problems.append(f"{case['name']}: '{key}' katalogda yok")
            continue
        value = float(str(raw).replace(",", "."))
        if not param.is_abnormal(value, sex):
            continue
        flagged.append(param.id)
        nutrition_key = param.nutrition_key(param.is_high(value, sex))
        if nutrition_key and nutrition_key not in protocols:
            protocols.append(nutrition_key)

    case["expected"]["must_flag"] = [k for k in intended if k in flagged]
    case["expected"]["key_protocols"] = protocols

    if is_control:
        if flagged:
            problems.append(f"{case['name']}: negatif kontrol ama {len(flagged)} sapma var: {flagged}")
    else:
        if not flagged:
            problems.append(f"{case['name']}: hiçbir parametre referans dışı değil (vaka etkisiz)")
        if not case["expected"]["must_flag"]:
            problems.append(f"{case['name']}: vakayı tanımlayan hiçbir değer sapma üretmedi")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Sadece doğrula, dosyayı yazma")
    args = parser.parse_args()

    cat = catalog_module.load(config.DATABASE_PATH)

    cases: list[dict] = []
    problems: list[str] = []
    index_domains = {meta["domain"] for meta in cat.indices.values()}

    for spec in ARCHETYPES:
        for index, (severity, factor) in enumerate(SEVERITIES):
            person = spec["people"][index % len(spec["people"])]
            case = build_case(spec, cat, severity, factor, person)
            problems.extend(derive_and_validate(case, spec["labs"], cat, is_control=False))
            case["expected"]["index_check"] = index_expectation(
                spec["domain"], False, True, index_domains
            )
            cases.append(case)

    for spec in CONTROLS:
        case = build_case(spec, cat, None, 1.0, spec["person"])
        problems.extend(derive_and_validate(case, spec["labs"], cat, is_control=True))
        case["expected"]["index_check"] = index_expectation(
            spec["domain"], True, bool(spec["labs"]), index_domains
        )
        cases.append(case)

    names = [c["name"] for c in cases]
    if len(names) != len(set(names)):
        problems.append("Mükerrer vaka adı var")

    if problems:
        print("DOĞRULAMA HATALARI:")
        for problem in problems:
            print(f"  x {problem}")
        return 1

    covered = {k for c in cases for k in c["expected"]["key_protocols"]}
    uncovered = sorted(set(cat.nutrition) - covered)
    domains = sorted({c["expected"]["primary_domain"] for c in cases})
    genders = [c["biometrics"]["cinsiyet"] for c in cases]
    ages = [int(c["biometrics"]["yas"]) for c in cases]
    flags = sum(len(c["expected"]["must_flag"]) for c in cases)

    print(f"OK  {len(cases)} vaka dogrulandi ({len(ARCHETYPES)} arketip x {len(SEVERITIES)} siddet "
          f"+ {len(CONTROLS)} negatif kontrol)")
    print(f"    protokol kapsami : {len(covered)}/{len(cat.nutrition)}")
    if uncovered:
        print(f"    kapsanmayan      : {', '.join(uncovered)}")
    print(f"    klinik alanlar   : {len(domains)} -> {', '.join(domains)}")
    print(f"    demografi        : {genders.count('male')} erkek / {genders.count('female')} kadin, "
          f"yas {min(ages)}-{max(ages)}")
    print(f"    toplam beklenen sapma noktasi: {flags}")

    if args.check:
        return 0

    with open(ROOT / "presets.json", "w", encoding="utf-8") as handle:
        json.dump(cases, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(f"->  presets.json yazildi ({len(cases)} vaka)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

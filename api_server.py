# -*- coding: utf-8 -*-
"""HealthScope — Klinik & Biyo-Nutrisyonel Çıkarım Sunucusu.

Çalıştırmak için:
    pip install -r requirements.txt
    python api_server.py            (ya da: uvicorn api_server:app --reload)

Makineye özgü tüm yollar `config.py` üzerinden ortam değişkenleriyle
yönetilir; `.env.example` dosyasına bakın.
"""
from __future__ import annotations

import io
import logging
import re
import threading
import time
from contextlib import asynccontextmanager
from typing import Any

import numpy as np
import torch
from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import catalog as catalog_module
import clinical_brief
import config
import indices as indices_module
import llm as llm_module

# OCR bağımlılıkları opsiyoneldir: kurulu değilse /analyze çalışmaya devam eder,
# yalnızca /upload-report 503 döner. Böylece sunucu kısmi kurulumda da ayağa kalkar.
try:
    import cv2
    from pdf2image import convert_from_bytes

    OCR_DEPS_ERROR: str | None = None
except ImportError as _exc:  # pragma: no cover - ortama bağlı
    cv2 = None  # type: ignore[assignment]
    convert_from_bytes = None  # type: ignore[assignment]
    OCR_DEPS_ERROR = f"OCR bağımlılıkları eksik ({_exc}). `pip install -r requirements.txt` çalıştırın."

# ── 1. LOGLAMA ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(threadName)s) %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("HealthScopeEngine")

ENGINE_VERSION = "3.1.0"

MEDICAL_DISCLAIMER = (
    "Bu çıktı bir tıbbi teşhis değildir. HealthScope, laboratuvar verilerini istatistiksel "
    "olarak yorumlayan bir karar DESTEK sistemidir ve hekim değerlendirmesinin yerine geçmez. "
    "Tedavi veya beslenme değişikliği yapmadan önce mutlaka doktorunuza danışın."
)

@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Yapılandırma: %s", config.describe())
    if config.EAGER_LOAD:
        # Modeller arka planda ısıtılır; sunucu anında ayağa kalkar ve
        # /status ilk saniyeden itibaren yanıt verir.
        threading.Thread(target=ai.warmup, name="model-warmup", daemon=True).start()
        if llm_engine.enabled:
            threading.Thread(target=llm_engine.warmup, name="llm-warmup", daemon=True).start()
    yield


app = FastAPI(
    title="HealthScope AI Clinical & Nutritional Inference Server",
    description=(
        "Kan tahlili parametrelerinden klinik çıkarım ve biyo-nutrisyonel öneri üreten "
        "karar destek motoru. " + MEDICAL_DISCLAIMER
    ),
    version=ENGINE_VERSION,
    lifespan=lifespan,
)

# Sağlık verisi taşındığı için joker origin kullanılmaz; izinli liste
# config üzerinden gelir. allow_credentials=False çünkü çerez/oturum yok.
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# ── 2. KLİNİK VERİTABANI ──────────────────────────────────────────────────
try:
    CATALOG = catalog_module.load(config.DATABASE_PATH)
    CATALOG_ERROR: str | None = None
except FileNotFoundError:
    CATALOG, CATALOG_ERROR = catalog_module.empty(), f"{config.DATABASE_PATH} bulunamadı."
    logger.critical(CATALOG_ERROR)
except (ValueError, KeyError) as exc:
    CATALOG, CATALOG_ERROR = catalog_module.empty(), f"database.json okunamadı: {exc}"
    logger.critical(CATALOG_ERROR)


# ── 3. GİRDİ MODELLERİ ────────────────────────────────────────────────────
class BiometricsModel(BaseModel):
    yas: int = Field(..., gt=0, lt=120)
    cinsiyet: str = Field(...)
    kilo: float = Field(..., gt=0, le=400)
    boy: float = Field(..., gt=0, le=260)

    model_config = {
        "json_schema_extra": {
            "example": {"yas": 22, "cinsiyet": "male", "kilo": 75.0, "boy": 180.0}
        }
    }


class MedicalHistoryModel(BaseModel):
    kronik: str = Field(default="Yok", max_length=500)
    alerjiler: list[str] = Field(default_factory=list, max_length=50)
    genetik_riskler: list[str] = Field(default_factory=list, max_length=50)

    model_config = {
        "json_schema_extra": {
            "example": {
                "kronik": "Hipertansiyon",
                "alerjiler": ["Ceviz", "Sarımsak"],
                "genetik_riskler": ["Ailede Diyabet Öyküsü"],
            }
        }
    }


class LabInput(BaseModel):
    values: dict[str, str | None] = Field(...)
    biometrics: BiometricsModel
    medical: MedicalHistoryModel

    model_config = {
        "json_schema_extra": {
            "example": {
                "values": {"ure": "78", "hgb": "9.2", "mcv": "75"},
                "biometrics": {"yas": 45, "cinsiyet": "male", "kilo": 95, "boy": 182},
                "medical": {"kronik": "Yok", "alerjiler": [], "genetik_riskler": []},
            }
        }
    }


# ── 4. YAPAY ZEKA MOTORU ──────────────────────────────────────────────────
class ClinicalAIEngine:
    """BERTurk fill-mask ve EasyOCR motorlarını tembel (lazy) yükler.

    Ağır modeller ilk kullanımda ya da arka plan ısıtmasıyla yüklenir; böylece
    sunucu saniyeler içinde ayağa kalkar ve `/status` her zaman yanıt verir.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.device_id = 0 if torch.cuda.is_available() else -1
        self.device_name = torch.cuda.get_device_name(0) if self.device_id == 0 else "CPU"
        self.nlp_model: Any = None
        self.reader: Any = None
        self.nlp_state = "not_loaded"
        self.ocr_state = "not_loaded"
        self.nlp_error: str | None = None
        self.ocr_error: str | None = None
        self.using_fine_tuned = False
        logger.info("Donanım: %s (device=%s)", self.device_name, self.device_id)

    # -- BERTurk -----------------------------------------------------------
    def get_nlp(self) -> Any:
        if self.nlp_model is None and self.nlp_state != "error":
            with self._lock:
                if self.nlp_model is None and self.nlp_state != "error":
                    self._load_nlp()
        return self.nlp_model

    def _load_nlp(self) -> None:
        from transformers import AutoModelForMaskedLM, AutoTokenizer, pipeline

        self.nlp_state = "loading"
        model_source = config.MODEL_PATH or config.BASE_MODEL
        try:
            logger.info("BERTurk yükleniyor: %s", model_source)
            # Tokenizer önce checkpoint'in kendi içinden okunur; fine-tune
            # çıktısı tokenizer.json içerdiği için bu yol internet gerektirmez
            # (jüri sunumunda çevrimdışı çalışabilmek kritik). Checkpoint'te
            # tokenizer yoksa Hub'daki temel modele düşülür.
            try:
                tokenizer = AutoTokenizer.from_pretrained(model_source)
            except (OSError, ValueError):
                logger.info("Checkpoint'te tokenizer yok, temel modelden alınıyor: %s", config.BASE_MODEL)
                tokenizer = AutoTokenizer.from_pretrained(config.BASE_MODEL)
            model = AutoModelForMaskedLM.from_pretrained(model_source)
            self.nlp_model = pipeline(
                "fill-mask", model=model, tokenizer=tokenizer, device=self.device_id
            )
            self.using_fine_tuned = config.MODEL_PATH is not None
            self.nlp_state = "ready"
            if not self.using_fine_tuned:
                logger.warning(
                    "HEALTHSCOPE_MODEL_PATH tanımlı değil; fine-tune edilmemiş temel model "
                    "kullanılıyor. Çıkarım kalitesi düşük olacaktır."
                )
            logger.info("BERTurk hazır (%s).", "fine-tuned" if self.using_fine_tuned else "temel model")
        except Exception as exc:  # noqa: BLE001 - başlatma hatası tek noktada raporlanır
            self.nlp_state, self.nlp_error = "error", str(exc)
            logger.critical("BERTurk yüklenemedi (%s): %s", model_source, exc)

    # -- EasyOCR -----------------------------------------------------------
    def get_reader(self) -> Any:
        if self.reader is None and self.ocr_state != "error":
            with self._lock:
                if self.reader is None and self.ocr_state != "error":
                    self._load_ocr()
        return self.reader

    def _load_ocr(self) -> None:
        if OCR_DEPS_ERROR:
            self.ocr_state, self.ocr_error = "error", OCR_DEPS_ERROR
            logger.error(OCR_DEPS_ERROR)
            return

        import easyocr

        self.ocr_state = "loading"
        try:
            logger.info("EasyOCR yükleniyor (tr, en)...")
            self.reader = easyocr.Reader(["tr", "en"], gpu=(self.device_id == 0))
            self.ocr_state = "ready"
            logger.info("EasyOCR hazır.")
        except Exception as exc:  # noqa: BLE001
            self.ocr_state, self.ocr_error = "error", str(exc)
            logger.critical("EasyOCR yüklenemedi: %s", exc)

    def warmup(self) -> None:
        self.get_nlp()
        self.get_reader()


ai = ClinicalAIEngine()

#: Hibrit akıl yürütme katmanı. `HEALTHSCOPE_LLM_PROVIDER=none` iken devre dışı
#: kalır ve sistem yalnızca BERTurk fill-mask ile çalışır.
llm_engine = llm_module.LLMEngine()


# ── 5. YARDIMCI FONKSİYONLAR ──────────────────────────────────────────────
#: BERT özel token'ları ve prompt yapısını bozabilecek karakterler.
_PROMPT_UNSAFE = re.compile(r"\[\s*(MASK|CLS|SEP|PAD|UNK)\s*\]", re.IGNORECASE)
_PROMPT_STRUCTURAL = re.compile(r"[\[\]{}<>|`]")


def sanitize_free_text(value: Any, limit: int = 180, fallback: str = "Bilinmiyor") -> str:
    """Kullanıcı metnini prompt'a girmeden önce zararsızlaştırır.

    Kullanıcı `[MASK]` ya da kendi talimatını enjekte ederek modelin
    çıkarımını yönlendirebilirdi; özel token'lar ve yapısal karakterler
    temizlenir, uzunluk sınırlanır.
    """
    text = str(value or "")
    text = _PROMPT_UNSAFE.sub(" ", text)
    text = _PROMPT_STRUCTURAL.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        text = text[:limit].rstrip() + "…"
    return text or fallback


def calculate_advanced_metrics(bio: BiometricsModel) -> dict[str, Any]:
    bmi = round(bio.kilo / ((bio.boy / 100) ** 2), 1)

    # Bazal Metabolizma Hızı — Mifflin-St Jeor
    if bio.cinsiyet.lower() in ("male", "erkek"):
        bmr = round(10 * bio.kilo + 6.25 * bio.boy - 5 * bio.yas + 5)
    else:
        bmr = round(10 * bio.kilo + 6.25 * bio.boy - 5 * bio.yas - 161)

    if bmi < 18.5:
        status_text = "Kaşeksi / Düşük Vücut Ağırlığı"
    elif bmi < 25:
        status_text = "Normal"
    elif bmi < 30:
        status_text = "Pre-Obezite (Metabolik Yük)"
    else:
        status_text = "Obezite (Kardiyovasküler & Endokrin Risk)"

    return {"bmi": bmi, "bmr": bmr, "status": status_text}


#: Modelin klinik olmayan / anlamsız token üretmesini engelleyen liste.
#: Tümü küçük harf — karşılaştırma da küçük harf üzerinden yapılır.
BANNED_TOKENS = (
    "tümör", "tumor", "kontrol", "sayım", "sayim", "oran", "risk", "yük", "protein",
    "test", "gelir", "ağırlık", "durum", "vaka", "bulgu", "sonuç", "değer", "seviye",
    "gösterge", "yaş", "depresyon", "zarar", "ölüm", "olum", "parametre", "faktör",
    "düzey", "tablo", "sendrom", "belirti", "sağlık", "serum", "kusur", "hastalık",
    "hastalik", "tanı", "tani", "klinik", "tedavi",
)

#: Obstetrik terimler — erkeklerde ve üreme çağı dışındaki hastalarda bloklanır.
BANNED_OBSTETRIC = ("gebe", "gebelik", "hamile", "hamilelik", "doğum", "abortus")

#: Obstetrik terimlerin klinik olarak mümkün olduğu yaş aralığı.
FERTILE_AGE_RANGE = (12, 55)


def map_prediction(token: str, score: float, gender: str, age: int | None = None) -> dict[str, Any] | None:
    """Ham model token'ını klinik terime çevirir; uygun değilse None döner."""
    word = token.strip().lower()

    banned = BANNED_TOKENS
    is_male = gender.lower() in ("male", "erkek")
    out_of_fertile_age = age is not None and not (FERTILE_AGE_RANGE[0] <= age <= FERTILE_AGE_RANGE[1])
    if is_male or out_of_fertile_age:
        # 68 yaşındaki bir hastaya "Gebelik" önermek klinik olarak imkânsızdır;
        # model bu token'ı yüksek skorla üretebildiği için burada elenir.
        banned = banned + BANNED_OBSTETRIC

    if len(word) < 3 or any(b in word for b in banned):
        return None

    # KAPALI KELİME DAĞARCIĞI: token yalnızca klinik sözlükte karşılığı varsa
    # kabul edilir. Eskiden bilinmeyen kelimeler `word.capitalize()` ile geri
    # döndürülüyordu; bu yüzden "Tespit", "Fonksiyon", "Dağılım" gibi teşhis
    # OLMAYAN kelimeler teşhis listesinde görünüyordu. Sözlük dışı token artık
    # elenir — model bir şey uyduramaz, yalnızca tanımlı klinik terimleri seçer.
    mapped = CATALOG.extended_dict.get(word) or CATALOG.clinical_dictionary.get(word)
    if not mapped:
        return None

    return {"diagnosis": mapped, "model_score": round(score * 100, 2), "raw_token": word}


def normalize_probabilities(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ham softmax skorlarını, elenen adaylar çıkarıldıktan sonra yeniden normalize eder.

    Önceki sürüm düşük skorları sabit 8 katıyla çarpıp %12.5-85 bandına
    sıkıştırıyordu; bu bilimsel olarak savunulamaz bir şişirmeydi.
    Artık gösterilen yüzde, "elenen adaylar hariç, kalan adaylar arasındaki
    göreli olasılık" anlamına gelir ve ham skor da yanıtta korunur.
    """
    total = sum(c["model_score"] for c in candidates)
    for candidate in candidates:
        candidate["probability"] = (
            round(candidate["model_score"] / total * 100, 1) if total > 0 else 0.0
        )
    return candidates


# ── 6. ENDPOINT'LER ───────────────────────────────────────────────────────
@app.get("/status")
def get_status() -> dict[str, Any]:
    """Gerçek zamanlı motor durumu — arayüzdeki kartlar bunu tüketir."""
    return {
        "engine_version": ENGINE_VERSION,
        "database_ok": CATALOG_ERROR is None,
        "database_error": CATALOG_ERROR,
        "catalog": CATALOG.as_summary(),
        "inference": {
            "state": ai.nlp_state,
            "error": ai.nlp_error,
            # Model henüz yüklenmediyse çalışma zamanı bayrağı False'tur; bu
            # durumda yapılandırmaya bakılır, aksi hâlde arayüz "fine-tune
            # edilmemiş model" uyarısını yanlışlıkla gösterir.
            "fine_tuned": ai.using_fine_tuned if ai.nlp_state == "ready" else (config.MODEL_PATH is not None),
            "checkpoint": config.describe()["model_checkpoint"],
            "base_model": config.BASE_MODEL,
        },
        "ocr": {
            "engine": "EasyOCR (tr, en)",
            "state": "error" if OCR_DEPS_ERROR else ai.ocr_state,
            "error": OCR_DEPS_ERROR or ai.ocr_error,
        },
        "hardware": {
            "device": ai.device_name,
            "cuda_available": torch.cuda.is_available(),
        },
        "limits": {
            "max_upload_mb": config.MAX_UPLOAD_MB,
            "max_pdf_pages": config.MAX_PDF_PAGES,
        },
        "narrative_engine": llm_engine.status(),
        "ocr_support": OCR_DEPS_ERROR is None,
        "pdf_support": OCR_DEPS_ERROR is None and config.POPPLER_PATH is not None,
        "disclaimer": MEDICAL_DISCLAIMER,
    }


# `def` (async değil) — ağır senkron iş FastAPI'nin threadpool'unda çalışır,
# böylece eşzamanlı istekler event loop'u bloklamaz.
@app.post("/analyze", status_code=status.HTTP_200_OK)
def analyze_comprehensive(input_data: LabInput) -> dict[str, Any]:
    start_time = time.time()

    if CATALOG_ERROR:
        raise HTTPException(status_code=503, detail=f"Klinik veritabanı yüklenemedi: {CATALOG_ERROR}")

    nlp = ai.get_nlp()
    if nlp is None:
        raise HTTPException(
            status_code=503,
            detail=f"Yapay zeka çekirdeği kullanılamıyor: {ai.nlp_error or 'model yükleniyor'}",
        )

    logger.info("Analiz isteği: %s yaş, %d parametre.", input_data.biometrics.yas, len(input_data.values))

    metrics = calculate_advanced_metrics(input_data.biometrics)

    # -- Sapma tespiti ----------------------------------------------------
    abnormal_findings: list[dict[str, Any]] = []
    unknown_parameters: list[str] = []
    #: Klinik indeks hesabı için sayıya çevrilmiş tüm değerler (normaller dahil).
    numeric_values: dict[str, float] = {}
    #: Referans aralıkları cinsiyete göre değişebilir (kreatinin, hemoglobin,
    #: ferritin...). Tek aralık kullanmak yanlış alarm üretiyordu.
    sex = input_data.biometrics.cinsiyet

    for key, raw_value in input_data.values.items():
        if raw_value is None or str(raw_value).strip() == "":
            continue

        param = CATALOG.get(key)
        if param is None:
            unknown_parameters.append(key)
            continue

        try:
            value = float(str(raw_value).replace(",", "."))
        except ValueError:
            unknown_parameters.append(key)
            continue

        numeric_values[param.id] = value

        if not param.is_abnormal(value, sex):
            continue

        is_high = param.is_high(value, sex)
        deviation = param.deviation_percentage(value, sex)

        # Sistem yükü için sapma, referans aralığı GENİŞLİĞİNE göre ölçülür.
        # Ham yüzde kullanmak, alt sınırı 0 olan parametrelerin (CRP 0-5) tüm
        # alanı domine etmesine yol açıyordu.
        low, high = param.range_for(sex)
        distance = (value - high) if is_high else (low - value)
        width = high - low
        severity = distance / width if width > 0 else distance

        abnormal_findings.append({
            "parameter": param.id.upper(),
            "label": param.label,
            "value": value,
            "unit": param.unit,
            "severity": round(severity, 3),
            "reference": param.reference_text(sex),
            "status": "Yüksek" if is_high else "Düşük",
            "deviation_percentage": deviation,
            "domain": param.domain,
            "nutrition_key": param.nutrition_key(is_high),
        })

    if unknown_parameters:
        logger.warning("Katalogda bulunmayan/geçersiz alanlar atlandı: %s", ", ".join(unknown_parameters))

    abnormal_findings.sort(key=lambda f: f["deviation_percentage"], reverse=True)

    # -- Klinik indeksler --------------------------------------------------
    # Tek tek parametrelerin göremediği örüntüleri yakalar (ör. De Ritis oranı
    # alkolik ve viral hepatiti ayırır). Tamamen deterministik ve kaynaklıdır.
    clinical_indices, unavailable_indices = indices_module.compute(
        CATALOG.indices,
        numeric_values,
        {"yas": input_data.biometrics.yas, "cinsiyet": input_data.biometrics.cinsiyet},
        CATALOG,
    )
    suggested_tests = indices_module.collect_suggested_tests(clinical_indices, CATALOG)
    if suggested_tests:
        logger.info(
            "  Ayırt edici test önerisi: %s",
            "; ".join(f"{t['label']} ({t['reason']})" for t in suggested_tests),
        )

    flagged_indices = [i for i in clinical_indices if i["level"] != "normal"]
    if flagged_indices:
        logger.info(
            "  %d klinik indeks dikkat çekti: %s",
            len(flagged_indices),
            ", ".join(f"{i['label']}={i['value']}{i['unit']} [{i['level']}]" for i in flagged_indices),
        )

    # -- Sistem yükü -------------------------------------------------------
    # Puanlama 118 vakada ölçülerek seçildi (ham yüzde %80 -> bu %86).
    ranked_domains = catalog_module.domain_scores(abnormal_findings)
    co_dominant = catalog_module.co_dominant_domains(ranked_domains)
    target_focus = ranked_domains[0][0] if ranked_domains else "Genel Metabolik Durum"
    dominant_domains = {domain: round(score, 3) for domain, score in ranked_domains}

    # -- Prompt kurgusu ---------------------------------------------------

    findings_text = ", ".join(
        f"{f['label']} %{f['deviation_percentage']} {f['status']}" for f in abnormal_findings[:10]
    ) or "Tüm parametreler fizyolojik referans aralığındadır"

    kronik = sanitize_free_text(input_data.medical.kronik, fallback="Bilinen kronik hastalık yok")
    genetics = sanitize_free_text(
        ", ".join(str(g) for g in input_data.medical.genetik_riskler if g), fallback="Bilinmiyor"
    )

    prompt = (
        f"Hasta: {input_data.biometrics.yas} yaşında. VKI: {metrics['bmi']} ({metrics['status']}). "
        f"Öykü: {kronik}. Genetik Risk: {genetics}. "
        f"Klinik Sapmalar: {findings_text}. "
        f"Bu veriler {target_focus} perspektifinden incelendiğinde en olası primer "
        f"{nlp.tokenizer.mask_token} tablosu düşünülmelidir."
    )

    # Çıkarım süresi ayrı ölçülür: terminalde modelin gerçekten çalıştığının
    # kanıtı olarak ham token skorlarıyla birlikte loglanır.
    inference_start = time.time()
    try:
        raw_outputs = nlp(prompt, top_k=20)
    except Exception as exc:  # noqa: BLE001
        logger.error("Model çıkarımı başarısız: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Model çıkarımı sırasında hata oluştu.") from exc
    inference_ms = round((time.time() - inference_start) * 1000, 1)

    logger.info(
        "  BERTurk çıkarımı tamamlandı: %s ms | prompt %s token | ham ilk 5: %s",
        inference_ms,
        len(nlp.tokenizer.tokenize(prompt)),
        ", ".join(f"{o['token_str']}={o['score'] * 100:.2f}%" for o in raw_outputs[:5]),
    )

    diagnoses: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw_outputs:
        mapped = map_prediction(
            item["token_str"], item["score"], input_data.biometrics.cinsiyet, input_data.biometrics.yas
        )
        if mapped and mapped["diagnosis"] not in seen:
            seen.add(mapped["diagnosis"])
            diagnoses.append(mapped)
            if len(diagnoses) == 4:
                break

    # Sağlıklı hastaya teşhis uydurulmaz. Eskiden hiçbir aday kalmadığında
    # "<alan> Kaynaklı Fonksiyonel Düzensizlik" diye bir tablo üretiliyordu;
    # tüm parametreleri normal olan bir kişide bu düpedüz yanlıştı.
    if not abnormal_findings:
        diagnoses = []
        inference_note = (
            "Girilen parametrelerin tamamı referans aralığındadır; "
            "dil modelinden klinik örüntü istenmemiştir."
        )
    elif not diagnoses:
        inference_note = (
            "Dil modeli, klinik sözlükte karşılığı olan bir örüntü üretemedi. "
            "Bulgular ve klinik indeksler geçerlidir."
        )
    else:
        inference_note = None

    normalize_probabilities(diagnoses)

    logger.info(
        "  Filtreden geçen %d aday: %s",
        len(diagnoses),
        " | ".join(f"{d['raw_token']} -> {d['diagnosis'][:38]} (%{d['probability']})" for d in diagnoses),
    )

    # -- Biyo-nutrisyonel protokol ----------------------------------------
    protocol_keys = [f["nutrition_key"] for f in abnormal_findings if f["nutrition_key"]]
    # İndeksler de protokol tetikleyebilir: tek tek parametreler normal görünse
    # bile örüntü anormalse (ör. HOMA-IR yüksek) beslenme önerisi üretilir.
    index_keys = [i["nutrition_key"] for i in clinical_indices if i["nutrition_key"]]
    protocol_keys.extend(index_keys)
    symptom_keys = CATALOG.match_symptom_protocols(input_data.medical.kronik)
    protocol_keys.extend(symptom_keys)

    allergens = [str(a).lower().strip() for a in input_data.medical.alerjiler if str(a).strip()]

    foods: list[str] = []
    compounds: list[str] = []
    synergies: list[str] = []
    inhibitors: list[str] = []
    excluded_foods: list[str] = []

    for key in dict.fromkeys(protocol_keys):
        protocol = CATALOG.protocol(key)
        if not protocol:
            continue
        compounds.extend(protocol["compounds"])
        synergies.append(protocol["synergy"])
        inhibitors.extend(protocol["inhibitors"])
        for food in protocol["foods"]:
            if any(allergen in food.lower() for allergen in allergens):
                excluded_foods.append(food)
            else:
                foods.append(food)

    unique = lambda items, limit: list(dict.fromkeys(items))[:limit]  # noqa: E731

    gender_text = "Erkek" if input_data.biometrics.cinsiyet.lower() in ("male", "erkek") else "Kadın"

    # Sapma yoksa özet de "sağlıklı" demeli; sapma varmış gibi cümle kurulmaz.
    if abnormal_findings:
        findings_sentence = (
            f"Tahlillerde {len(abnormal_findings)} parametre referans aralığının dışında bulundu "
            f"ve en yoğun sapma {target_focus} alanında görüldü. "
        )
    else:
        findings_sentence = (
            "Girilen parametrelerin tamamı referans aralığındadır; herhangi bir sapma "
            "saptanmamıştır. "
        )

    if flagged_indices:
        index_sentence = (
            f"Hesaplanan {len(clinical_indices)} klinik indeksten {len(flagged_indices)} tanesi "
            f"dikkat çekici bulundu ({', '.join(i['label'] for i in flagged_indices[:3])}). "
        )
    elif clinical_indices:
        index_sentence = f"Hesaplanan {len(clinical_indices)} klinik indeksin tamamı normal sınırlardadır. "
    else:
        index_sentence = ""

    if diagnoses:
        inference_sentence = (
            f"Dil modeli, klinik öykü ile laboratuvar verilerini birlikte değerlendirerek "
            f"öncelikli olarak '{diagnoses[0]['diagnosis']}' yönünde bir örüntüye işaret etmektedir."
        )
    elif abnormal_findings:
        inference_sentence = (
            "Dil modeli, klinik sözlükte karşılığı olan belirgin bir örüntü üretemedi; "
            "değerlendirme bulgulara ve klinik indekslere dayanmaktadır."
        )
    else:
        inference_sentence = (
            "Sapma bulunmadığı için klinik örüntü çıkarımı yapılmamıştır."
        )

    summary_text = (
        f"HealthScope çıkarım motoru, {input_data.biometrics.yas} yaşındaki {gender_text} hastanın "
        f"{len(input_data.values)} parametrelik verisini analiz etti. Fizyolojik durum "
        f"'{metrics['status']}' olarak sınıflandırıldı; günlük bazal enerji ihtiyacı "
        f"{metrics['bmr']} kcal hesaplandı. "
        + findings_sentence + index_sentence + inference_sentence
    )

    # ── HİBRİT KATMAN ────────────────────────────────────────────────────
    # Kural motorunun çıkardığı öznitelikler yapılandırılmış bir klinik özete
    # çevrilir; üretken model bunun ÜZERİNDE akıl yürütür. Ham sapma listesi
    # yerine işlenmiş bulgu verildiği için model çok daha isabetli çalışır.
    # Katman kapalıysa ya da hata verirse analiz sonucu değişmeden döner.
    clinical_summary = clinical_brief.build(
        biometrics={"yas": input_data.biometrics.yas, "cinsiyet": input_data.biometrics.cinsiyet},
        metrics=metrics,
        history=kronik,
        genetics=genetics,
        allergies=allergens,
        abnormal_findings=abnormal_findings,
        clinical_indices=clinical_indices,
        suggested_tests=suggested_tests,
        primary_domain=target_focus,
        evaluated_count=len(input_data.values) - len(unknown_parameters),
    )

    narrative: dict[str, Any] | None = None
    if llm_engine.enabled:
        result = llm_engine.evaluate(clinical_brief.SYSTEM_PROMPT, clinical_summary)
        narrative = result.as_dict()
        if result.ok:
            logger.info("  Üretken değerlendirme üretildi (%s ms).", narrative["elapsed_ms"])

    process_time = round((time.time() - start_time) * 1000, 1)

    return {
        "engine_version": ENGINE_VERSION,
        "disclaimer": MEDICAL_DISCLAIMER,
        #: Hibrit katman: yapılandırılmış klinik özet + üretken değerlendirme.
        #: `narrative` None ise katman kapalıdır; arayüz bölümü göstermez.
        "clinical_brief": clinical_summary,
        "narrative": narrative,
        "timestamp": process_time,
        "processing_ms": process_time,
        "executive_summary": summary_text,
        "physiological_metrics": metrics,
        "clinical_indices": {
            "computed": clinical_indices,
            "flagged_count": len(flagged_indices),
            "unavailable": unavailable_indices,
            #: Örüntü belirsizse ayırt edici test önerilir (ör. AST yüksek ama
            #: GGT normalse, kas mı karaciğer mi sorusunu CK çözer).
            "suggested_tests": suggested_tests,
            "basis": (
                "Klinik indeksler, literatürde tanımlı formüllerle hesaplanan deterministik "
                "değerlerdir; dil modelinden bağımsızdır ve her biri kaynak gösterilmiştir."
            ),
        },
        "clinical_findings": {
            "primary_focus_domain": target_focus,
            "abnormal_parameters_detected": abnormal_findings,
            "evaluated_parameter_count": len(input_data.values) - len(unknown_parameters),
            "skipped_parameters": unknown_parameters,
            "domain_load": dominant_domains,
            "co_dominant_domains": co_dominant,
        },
        "ai_inference_results": {
            "probabilities_chart_data": diagnoses,
            "fine_tuned_model": ai.using_fine_tuned,
            "inference_ms": inference_ms,
            "device": ai.device_name,
            "model_checkpoint": config.describe()["model_checkpoint"] or config.BASE_MODEL,
            "candidates_considered": len(raw_outputs),
            "prompt_token_count": len(nlp.tokenizer.tokenize(prompt)),
            "probability_basis": (
                "Yüzdeler, elenen adaylar çıkarıldıktan sonra kalan adaylar arasında yeniden "
                "normalize edilmiş model skorlarıdır; klinik olasılık değildir."
            ),
            "note": inference_note,
            "confidence_status": (
                "Değerlendirme dışı"
                if not diagnoses
                else "Yüksek"
                if diagnoses[0]["model_score"] >= 5
                else "Düşük (zayıf model sinyali)"
            ),
        },
        "bio_nutritional_protocol": {
            "target_active_compounds": unique(compounds, 8),
            "allergy_cleared_foods": unique(foods, 10),
            "biochemical_synergies": unique(synergies, 4),
            "contraindicated_inhibitors": unique(inhibitors, 6),
            "excluded_by_allergy": unique(excluded_foods, 10),
            "excluded_allergens_count": len(allergens),
            "matched_protocols": list(dict.fromkeys(protocol_keys)),
            "symptom_protocols": symptom_keys,
        },
    }


class ChatTurn(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., max_length=4000)


class ChatRequest(BaseModel):
    """Sohbet isteği.

    Sunucu DURUMSUZDUR: hastanın bulguları (`brief`) her istekte yeniden
    gönderilir. Böylece sağlık verisi sunucuda saklanmaz ve statik olarak
    yayınlanan arayüzle de uyumlu kalır.
    """

    brief: str = Field(..., max_length=12000)
    question: str = Field(..., min_length=1, max_length=500)
    history: list[ChatTurn] = Field(default_factory=list, max_length=20)


#: Modele verilecek azami geçmiş turu. Bağlam şiştikçe model dağılır ve
#: yanıt süresi uzar; son turlar en alakalı olanlardır.
MAX_CHAT_HISTORY_TURNS = 6


@app.post("/chat")
def chat(request: ChatRequest) -> dict[str, Any]:
    """Hastanın kendi bulguları hakkında soru sormasını sağlar."""
    if not llm_engine.enabled:
        raise HTTPException(
            status_code=503,
            detail="Sohbet için üretken model gerekli. HEALTHSCOPE_LLM_PROVIDER ayarlayın.",
        )

    question = sanitize_free_text(request.question, limit=500, fallback="")
    if not question:
        raise HTTPException(status_code=400, detail="Soru boş.")

    messages: list[dict[str, str]] = [
        {"role": "system", "content": clinical_brief.CHAT_SYSTEM_PROMPT},
        {"role": "user", "content": clinical_brief.build_chat_context(request.brief)},
        {"role": "assistant", "content": "Bulguları inceledim. Sorunuzu sorabilirsiniz."},
    ]
    for turn in request.history[-MAX_CHAT_HISTORY_TURNS * 2 :]:
        # Geçmişteki kullanıcı mesajları da temizlenir: enjeksiyon bir önceki
        # turda gelmiş olabilir.
        content = (
            sanitize_free_text(turn.content, limit=500, fallback="")
            if turn.role == "user"
            else turn.content
        )
        if content:
            messages.append({"role": turn.role, "content": content})
    messages.append({"role": "user", "content": question})

    logger.info("Sohbet sorusu (%d geçmiş tur): %s", len(request.history), question[:80])
    result = llm_engine.converse(messages)

    if not result.ok:
        raise HTTPException(status_code=503, detail=result.error or "Yanıt üretilemedi.")

    return {
        "answer": result.text,
        "model": result.model,
        "elapsed_ms": result.elapsed_ms,
        "disclaimer": MEDICAL_DISCLAIMER,
    }


@app.get("/chat/suggestions")
def chat_suggestions() -> dict[str, Any]:
    """Arayüzde gösterilen hazır sorular."""
    return {"questions": list(clinical_brief.SUGGESTED_QUESTIONS)}


@app.post("/upload-report")
def upload_report(file: UploadFile = File(...)) -> dict[str, Any]:
    """Tahlil raporundan (PDF veya görsel) parametre değerlerini çıkarır."""
    if CATALOG_ERROR:
        raise HTTPException(status_code=503, detail=f"Klinik veritabanı yüklenemedi: {CATALOG_ERROR}")
    if OCR_DEPS_ERROR:
        raise HTTPException(status_code=503, detail=OCR_DEPS_ERROR)

    reader = ai.get_reader()
    if reader is None:
        raise HTTPException(
            status_code=503, detail=f"OCR motoru kullanılamıyor: {ai.ocr_error or 'yükleniyor'}"
        )

    # `def` endpoint olduğu için dosya senkron okunur; boyut sınırı DoS'a karşı.
    contents = file.file.read(config.MAX_UPLOAD_BYTES + 1)
    if len(contents) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Dosya çok büyük. Üst sınır {config.MAX_UPLOAD_MB} MB.",
        )
    if not contents:
        raise HTTPException(status_code=400, detail="Dosya boş.")

    filename = (file.filename or "").lower()
    content_type = file.content_type or ""
    images: list[np.ndarray] = []

    if filename.endswith(".pdf") or content_type == "application/pdf":
        if config.POPPLER_PATH is None:
            raise HTTPException(
                status_code=503,
                detail=(
                    "PDF desteği kapalı: Poppler bulunamadı. HEALTHSCOPE_POPPLER_PATH ayarlayın "
                    "ya da raporu görsel (PNG/JPG) olarak yükleyin."
                ),
            )
        try:
            pages = convert_from_bytes(
                contents, poppler_path=config.POPPLER_PATH, last_page=config.MAX_PDF_PAGES
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("PDF dönüştürme hatası: %s", exc)
            raise HTTPException(status_code=400, detail=f"PDF resme dönüştürülemedi: {exc}") from exc

        if not pages:
            raise HTTPException(status_code=400, detail="PDF dosyası boş veya okunamadı.")

        for page in pages:
            buffer = io.BytesIO()
            page.save(buffer, format="PNG")
            decoded = cv2.imdecode(np.frombuffer(buffer.getvalue(), np.uint8), cv2.IMREAD_COLOR)
            if decoded is not None:
                images.append(decoded)

    elif filename.endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp")) or content_type.startswith("image/"):
        decoded = cv2.imdecode(np.frombuffer(contents, np.uint8), cv2.IMREAD_COLOR)
        if decoded is not None:
            images.append(decoded)
    else:
        raise HTTPException(
            status_code=400, detail="Desteklenmeyen dosya formatı. PDF, PNG veya JPG yükleyin."
        )

    if not images:
        raise HTTPException(status_code=400, detail="Dosya içeriği görsel olarak çözümlenemedi.")

    try:
        full_text = "\n".join(_read_page_text(reader, image) for image in images).upper()
    except Exception as exc:  # noqa: BLE001
        logger.error("OCR hatası: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"OCR işleme hatası: {exc}") from exc

    extracted = CATALOG.extract_values(full_text)
    if not extracted:
        logger.warning("OCR çalıştı ama parametre eşleşmedi. İlk 300 karakter: %s", full_text[:300])

    # Şüpheli okumalar: ondalık ayraç kaybı gibi hatalar burada yakalanır.
    # Değer forma yine de yazılır ama kullanıcıdan teyit istenir.
    suspects = CATALOG.detect_suspicious(extracted)
    if suspects:
        logger.warning(
            "OCR şüpheli okuma: %s",
            "; ".join(f"{s['parameter']}={s['value']} ({s['reason']})" for s in suspects),
        )

    return {
        "status": "success",
        "extracted": extracted,
        "page_count": len(images),
        "matched_count": len(extracted),
        "suspects": suspects,
        "ocr_engine": "EasyOCR (tr, en)",
        "notice": (
            "OCR sonuçları hatalı okuma içerebilir. Analizi başlatmadan önce forma dolan "
            "değerleri raporunuzla karşılaştırıp doğrulayın."
        ),
    }


def _read_page_text(reader: Any, image: np.ndarray) -> str:
    """Tek bir sayfa görselini satır düzenini koruyarak metne çevirir."""
    resized = cv2.resize(image, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)

    boxes = [
        ((bbox[0][1] + bbox[2][1]) / 2, bbox[0][0], text)
        for bbox, text, _ in reader.readtext(gray, detail=1)
    ]
    boxes.sort(key=lambda b: b[0])

    lines: list[str] = []
    current: list[tuple[float, float, str]] = []
    current_y: float | None = None
    y_tolerance = 20

    for box in boxes:
        y_center = box[0]
        if current_y is None or abs(y_center - current_y) <= y_tolerance:
            if current_y is None:
                current_y = y_center
            current.append(box)
        else:
            current.sort(key=lambda b: b[1])
            lines.append(" ".join(b[2] for b in current))
            current, current_y = [box], y_center

    if current:
        current.sort(key=lambda b: b[1])
        lines.append(" ".join(b[2] for b in current))

    return "\n".join(lines)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api_server:app", host=config.HOST, port=config.PORT, reload=True)

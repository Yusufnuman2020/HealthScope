# -*- coding: utf-8 -*-
"""HealthScope çalışma zamanı yapılandırması.

Tüm makineye özgü yollar buradan, ortam değişkenleriyle yönetilir.
Değer verilmezse proje dizinine göre makul varsayılanlar otomatik bulunur;
böylece proje başka bir makineye taşındığında kod değiştirmek gerekmez.

Ayarlar için proje kökünde bir `.env` dosyası oluşturabilirsiniz
(örnek için `.env.example` dosyasına bakın).
"""
import os
import logging
from pathlib import Path

logger = logging.getLogger("HealthScopeEngine.config")

BASE_DIR = Path(__file__).resolve().parent

# .env dosyası varsa yükle (python-dotenv kurulu değilse sessizce atlanır)
try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
except ImportError:  # pragma: no cover - opsiyonel bağımlılık
    pass


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _env_int(name: str, default: int) -> int:
    raw = _env(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("%s sayıya çevrilemedi (%r), varsayılan %s kullanılıyor.", name, raw, default)
        return default


def _find_poppler() -> str | None:
    """Proje içindeki POPPLER klasöründe `bin` dizinini arar.

    Sürüm numarası klasör adına gömülü olduğu için (Release-26.02.0-0/...)
    yol sabit yazılmaz, glob ile bulunur.
    """
    root = BASE_DIR / "POPPLER"
    if not root.is_dir():
        return None
    for candidate in sorted(root.rglob("bin")):
        if candidate.is_dir() and any(candidate.glob("pdftoppm*")):
            return str(candidate)
    return None


# ── Yollar ────────────────────────────────────────────────────────────────
#: pdf2image için Poppler `bin` dizini. None ise sistem PATH'i kullanılır.
POPPLER_PATH = _env("HEALTHSCOPE_POPPLER_PATH") or _find_poppler()

#: Fine-tune edilmiş BERTurk checkpoint dizini. Yoksa temel model kullanılır.
MODEL_PATH = _env("HEALTHSCOPE_MODEL_PATH")

#: Tokenizer / yedek model (HuggingFace Hub kimliği).
BASE_MODEL = _env("HEALTHSCOPE_BASE_MODEL", "dbmdz/bert-base-turkish-cased")

#: Klinik veritabanı (parametre kataloğu + beslenme protokolleri).
DATABASE_PATH = Path(_env("HEALTHSCOPE_DATABASE_PATH") or (BASE_DIR / "database.json"))

# ── Sunucu ────────────────────────────────────────────────────────────────
HOST = _env("HEALTHSCOPE_HOST", "127.0.0.1")
PORT = _env_int("HEALTHSCOPE_PORT", 8000)

#: Virgülle ayrılmış izinli origin listesi. Sağlık verisi taşındığı için
#: joker (*) varsayılan DEĞİLDİR.
CORS_ORIGINS = [
    origin.strip()
    for origin in (_env("HEALTHSCOPE_CORS_ORIGINS") or "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if origin.strip()
]

#: OCR yüklemeleri için üst sınır (MB). DoS yüzeyini daraltır.
MAX_UPLOAD_MB = _env_int("HEALTHSCOPE_MAX_UPLOAD_MB", 10)
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024

#: OCR'a gönderilecek azami PDF sayfa sayısı.
MAX_PDF_PAGES = _env_int("HEALTHSCOPE_MAX_PDF_PAGES", 15)

#: True ise model süreç başlarken arka planda ısıtılır.
EAGER_LOAD = (_env("HEALTHSCOPE_EAGER_LOAD", "1") or "1").lower() in ("1", "true", "yes")


# ── Hibrit üretken dil modeli (opsiyonel) ─────────────────────────────────
# Kural motorunun çıkardığı klinik öznitelikler üzerinde akıl yürüten katman.
# Kapalıysa (`none`) sistem eskisi gibi yalnızca BERTurk fill-mask kullanır;
# yani bu özellik hiçbir şeyi bozmadan eklenir.
#
#   none              -> kapalı (varsayılan)
#   local             -> transformers ile yerel causal LM
#   openai-compatible -> Ollama / LM Studio / bulut uç noktası
LLM_PROVIDER = (_env("HEALTHSCOPE_LLM_PROVIDER", "none") or "none").lower()

#: Yerel sağlayıcı için HuggingFace kimliği, uzak sağlayıcı için model adı.
LLM_MODEL = _env("HEALTHSCOPE_LLM_MODEL", "Qwen/Qwen2.5-3B-Instruct")

#: openai-compatible sağlayıcı için taban adres (ör. http://localhost:11434/v1).
LLM_BASE_URL = _env("HEALTHSCOPE_LLM_BASE_URL")

#: openai-compatible sağlayıcı için API anahtarı (yerel sunucularda gerekmez).
LLM_API_KEY = _env("HEALTHSCOPE_LLM_API_KEY")

#: 4-bit niceleme dener (bitsandbytes gerekir). 8 GB VRAM'de 7B modeli sığdırır.
LLM_QUANTIZE = (_env("HEALTHSCOPE_LLM_QUANTIZE", "1") or "1").lower() in ("1", "true", "yes")

LLM_MAX_NEW_TOKENS = _env_int("HEALTHSCOPE_LLM_MAX_NEW_TOKENS", 320)

#: Tekrar cezası. 1.0 = kapalı. Ölçümde 1.0 ve 1.15 karşılaştırıldı; ikisi de
#: kabul edilebilir çıktı verdi, 1.0 konu isabetinde bir miktar önde kaldı.
LLM_REPETITION_PENALTY = float(_env("HEALTHSCOPE_LLM_REPETITION_PENALTY", "1.0") or 1.0)
LLM_TIMEOUT_SECONDS = _env_int("HEALTHSCOPE_LLM_TIMEOUT", 120)


def describe() -> dict:
    """Loglama ve /status için hassas olmayan yapılandırma özeti."""
    return {
        "poppler_configured": POPPLER_PATH is not None,
        "model_checkpoint": Path(MODEL_PATH).name if MODEL_PATH else None,
        "base_model": BASE_MODEL,
        "database": DATABASE_PATH.name,
        "cors_origins": CORS_ORIGINS,
        "max_upload_mb": MAX_UPLOAD_MB,
        "llm_provider": LLM_PROVIDER,
        "llm_model": LLM_MODEL if LLM_PROVIDER != "none" else None,
    }

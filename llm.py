# -*- coding: utf-8 -*-
"""Üretken dil modeli katmanı (hibrit mimarinin akıl yürütme adımı).

`clinical_brief.py` kural motorunun bulgularını yapılandırılmış bir metne
çevirir; bu modül o metni bir dil modeline verip gerekçeli değerlendirme alır.

Tasarım ilkeleri:
  * TAMAMEN OPSİYONEL. Sağlayıcı `none` ise ya da model yüklenemezse
    `/analyze` eskisi gibi çalışır — hiçbir şey bozulmaz.
  * TEMBEL YÜKLEME. Ağır model yalnızca ilk kullanımda belleğe alınır.
  * SAĞLAYICI BAĞIMSIZ. Yerel (transformers) ve OpenAI uyumlu HTTP uç noktası
    aynı arayüzü paylaşır; böylece yerel model ile bulut modeli aynı
    kıyaslama setinde karşılaştırılabilir.
"""
from __future__ import annotations

import json
import logging
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import config

logger = logging.getLogger("HealthScopeEngine.llm")


def model_label() -> str:
    """Arayüzde gösterilecek kısa model adı.

    Yerel model bir dosya yolu olabilir; tam Windows yolunu ekrana basmak
    hem çirkin hem de kullanıcının klasör yapısını sızdırır. Yol verilmişse
    yalnızca klasör adı gösterilir.
    """
    raw = config.LLM_MODEL or "-"
    if any(sep in raw for sep in ("\\", "/")):
        return Path(raw).name
    return raw


class LLMResult:
    """Bir üretim denemesinin sonucu."""

    def __init__(
        self,
        text: str | None,
        *,
        model: str,
        provider: str,
        elapsed_ms: float,
        error: str | None = None,
    ):
        self.text = text
        self.model = model
        self.provider = provider
        self.elapsed_ms = elapsed_ms
        self.error = error

    @property
    def ok(self) -> bool:
        return self.text is not None and self.error is None

    def as_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "model": self.model,
            "provider": self.provider,
            "elapsed_ms": round(self.elapsed_ms, 1),
            "error": self.error,
        }


class BaseProvider:
    name = "base"

    def generate_messages(self, messages: list[dict[str, str]]) -> str:  # pragma: no cover
        """Çok turlu mesaj listesinden yanıt üretir — temel arayüz."""
        raise NotImplementedError

    def generate(self, system: str, user: str) -> str:
        """Tek turluk kısayol; sohbet ve tek seferlik üretim aynı yolu kullanır."""
        return self.generate_messages(
            [{"role": "system", "content": system}, {"role": "user", "content": user}]
        )

    def describe(self) -> dict[str, Any]:
        return {"provider": self.name, "model": model_label()}


# ── Yerel sağlayıcı ───────────────────────────────────────────────────────
class LocalProvider(BaseProvider):
    """transformers ile yerel causal LM.

    8 GB VRAM hedefiyle önce 4-bit niceleme denenir; bitsandbytes yoksa ya da
    Windows'ta çalışmazsa fp16'ya düşülür. Hiçbiri olmazsa CPU'ya düşer —
    yavaş ama çalışır.
    """

    name = "local"

    def __init__(self) -> None:
        self._pipe: Any = None
        self._lock = threading.Lock()
        self._loaded_with = "not_loaded"

    def _load(self) -> None:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        model_id = config.LLM_MODEL
        tokenizer = AutoTokenizer.from_pretrained(model_id)

        kwargs: dict[str, Any] = {"dtype": torch.float16, "device_map": "auto"}
        loaded_with = "fp16"

        if config.LLM_QUANTIZE and torch.cuda.is_available():
            try:
                from transformers import BitsAndBytesConfig

                kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_quant_type="nf4",
                )
                loaded_with = "4bit"
            except ImportError:
                logger.warning("bitsandbytes yok; fp16 ile yükleniyor (daha çok VRAM gerekir).")

        if not torch.cuda.is_available():
            kwargs = {"dtype": torch.float32}
            loaded_with = "cpu-fp32"
            logger.warning("CUDA yok; üretken model CPU'da çalışacak (yavaş).")

        logger.info("Üretken model yükleniyor: %s (%s)", model_id, loaded_with)
        model = AutoModelForCausalLM.from_pretrained(model_id, **kwargs)
        model.eval()

        self._tokenizer = tokenizer
        self._model = model
        self._loaded_with = loaded_with
        logger.info("Üretken model hazır (%s).", loaded_with)

    def ensure_loaded(self) -> None:
        if self._loaded_with in ("not_loaded",):
            with self._lock:
                if self._loaded_with == "not_loaded":
                    self._load()

    def generate_messages(self, messages: list[dict[str, str]]) -> str:
        import torch

        self.ensure_loaded()
        prompt = self._tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self._tokenizer(prompt, return_tensors="pt").to(self._model.device)

        with torch.no_grad():
            # Ayarlar ölçümle seçildi (bkz. clinical_brief.SYSTEM_PROMPT notu):
            # greedy çözümleme aynı girdide aynı çıktıyı verir — klinik bir
            # araçta tekrarlanabilirlik şart. `no_repeat_ngram_size` denendi ve
            # kullanılmadı: zorunlu feragat cümlesini de engelliyordu.
            output = self._model.generate(
                **inputs,
                max_new_tokens=config.LLM_MAX_NEW_TOKENS,
                do_sample=False,
                repetition_penalty=config.LLM_REPETITION_PENALTY,
                pad_token_id=self._tokenizer.eos_token_id,
            )

        generated = output[0][inputs["input_ids"].shape[-1] :]
        return self._tokenizer.decode(generated, skip_special_tokens=True).strip()

    def describe(self) -> dict[str, Any]:
        return {"provider": self.name, "model": model_label(), "precision": self._loaded_with}


# ── OpenAI uyumlu sağlayıcı ───────────────────────────────────────────────
class OpenAICompatibleProvider(BaseProvider):
    """Ollama, LM Studio, vLLM ya da bulut uç noktaları.

    Ek bağımlılık gerektirmez — standart kütüphaneyle HTTP çağrısı yapar.
    """

    name = "openai-compatible"

    def generate_messages(self, messages: list[dict[str, str]]) -> str:
        if not config.LLM_BASE_URL:
            raise RuntimeError("HEALTHSCOPE_LLM_BASE_URL tanımlı değil.")

        payload = {
            # DİKKAT: burada gerçek model kimliği gitmeli; `model_label()`
            # yalnızca arayüzde gösterim içindir.
            "model": config.LLM_MODEL,
            "messages": messages,
            "temperature": 0,
            "max_tokens": config.LLM_MAX_NEW_TOKENS,
        }
        headers = {"Content-Type": "application/json"}
        if config.LLM_API_KEY:
            headers["Authorization"] = f"Bearer {config.LLM_API_KEY}"

        request = urllib.request.Request(
            f"{config.LLM_BASE_URL.rstrip('/')}/chat/completions",
            json.dumps(payload).encode("utf-8"),
            headers,
        )
        with urllib.request.urlopen(request, timeout=config.LLM_TIMEOUT_SECONDS) as response:
            body = json.load(response)
        return body["choices"][0]["message"]["content"].strip()


# ── Motor ─────────────────────────────────────────────────────────────────
class LLMEngine:
    """Sağlayıcıyı seçer, hataları yutar ve durum bilgisi verir."""

    def __init__(self) -> None:
        self.provider: BaseProvider | None = None
        self.state = "disabled"
        self.error: str | None = None

        if config.LLM_PROVIDER == "local":
            self.provider = LocalProvider()
            self.state = "not_loaded"
        elif config.LLM_PROVIDER == "openai-compatible":
            self.provider = OpenAICompatibleProvider()
            self.state = "ready"
        elif config.LLM_PROVIDER != "none":
            self.error = f"Bilinmeyen sağlayıcı: {config.LLM_PROVIDER}"
            self.state = "error"

    @property
    def enabled(self) -> bool:
        return self.provider is not None

    def warmup(self) -> None:
        if isinstance(self.provider, LocalProvider):
            try:
                self.provider.ensure_loaded()
                self.state = "ready"
            except Exception as exc:  # noqa: BLE001 - başlatma hatası tek noktada
                self.state, self.error = "error", str(exc)
                logger.error("Üretken model yüklenemedi: %s", exc)

    def evaluate(self, system: str, user: str) -> LLMResult:
        """Tek turluk değerlendirme üretir."""
        return self.converse([{"role": "system", "content": system}, {"role": "user", "content": user}])

    def converse(self, messages: list[dict[str, str]]) -> LLMResult:
        """Çok turlu yanıt üretir. Hata durumunda ASLA istisna fırlatmaz —
        dil modeli katmanı çökse bile çağıran taraf çalışmaya devam eder."""
        started = time.time()
        if not self.provider:
            return LLMResult(None, model="-", provider="none", elapsed_ms=0.0, error="Sağlayıcı kapalı")

        try:
            text = self.provider.generate_messages(messages)
            self.state = "ready"
            return LLMResult(
                text,
                model=model_label(),
                provider=self.provider.name,
                elapsed_ms=(time.time() - started) * 1000,
            )
        except (urllib.error.URLError, TimeoutError) as exc:
            message = f"Uç noktaya ulaşılamadı: {exc}"
        except Exception as exc:  # noqa: BLE001
            message = str(exc)

        self.state, self.error = "error", message
        logger.error("Üretken model çıkarımı başarısız: %s", message)
        return LLMResult(
            None,
            model=model_label(),
            provider=self.provider.name,
            elapsed_ms=(time.time() - started) * 1000,
            error=message,
        )

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "state": self.state,
            "error": self.error,
            **(self.provider.describe() if self.provider else {"provider": "none", "model": None}),
        }

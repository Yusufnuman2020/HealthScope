/**
 * Backend istemcisi.
 *
 * Adres `NEXT_PUBLIC_API_URL` ile yapılandırılır ve build sırasında bundle'a
 * gömülür (statik export'ta çalışma zamanı ortam değişkeni okunamaz).
 * Tanımlı değilse yerel geliştirme sunucusu varsayılır — GitHub Pages gibi
 * statik bir yayında bu adrese ulaşılamayacağı için arayüz `useBackendStatus`
 * üzerinden "çevrimdışı" uyarısı gösterir.
 */
"use client";

import { useCallback, useEffect, useState } from "react";

export const API_BASE_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

export const MEDICAL_DISCLAIMER =
  "Bu çıktı bir tıbbi teşhis değildir. HealthScope, laboratuvar verilerini istatistiksel olarak " +
  "yorumlayan bir karar DESTEK sistemidir ve hekim değerlendirmesinin yerine geçmez. " +
  "Tedavi veya beslenme değişikliği yapmadan önce mutlaka doktorunuza danışın.";

// ── Sunucu yanıt tipleri ──────────────────────────────────────────────────
export interface BackendStatus {
  engine_version: string;
  database_ok: boolean;
  database_error: string | null;
  catalog: {
    parameter_count: number;
    group_count: number;
    nutrition_protocol_count: number;
    symptom_protocol_count: number;
    clinical_term_count: number;
  };
  inference: {
    state: "not_loaded" | "loading" | "ready" | "error";
    error: string | null;
    fine_tuned: boolean;
    checkpoint: string | null;
    base_model: string;
  };
  ocr: { engine: string; state: string; error: string | null };
  /** Hibrit üretken katman — kapalıysa `enabled: false`. */
  narrative_engine?: {
    enabled: boolean;
    state: "disabled" | "not_loaded" | "loading" | "ready" | "error";
    error: string | null;
    provider: string;
    model: string | null;
    precision?: string;
  };
  hardware: { device: string; cuda_available: boolean };
  limits: { max_upload_mb: number; max_pdf_pages: number };
  ocr_support: boolean;
  pdf_support: boolean;
  disclaimer: string;
}

export interface AbnormalParameter {
  parameter: string;
  label: string;
  value: number;
  unit: string;
  /**
   * Sapmanın referans aralığı genişliğine oranı. Sistem yükü ve anatomik
   * şema bunu kullanır; ham yüzde aşırı değerlerde çarpık sonuç veriyordu.
   */
  severity: number;
  reference: string;
  status: "Yüksek" | "Düşük";
  deviation_percentage: number;
  domain: string;
  nutrition_key: string | null;
}

export interface DiagnosisCandidate {
  diagnosis: string;
  probability: number;
  model_score: number;
  raw_token: string;
}

export type IndexLevel = "normal" | "borderline" | "high" | "critical";

export interface ClinicalIndex {
  id: string;
  label: string;
  full_name: string;
  domain: string;
  value: number;
  unit: string;
  level: IndexLevel;
  interpretation: string;
  /** İnsan okunur formül metni — jüriye "nasıl hesaplandı" sorusunun cevabı. */
  formula: string;
  reference: string;
  inputs: Record<string, number>;
  nutrition_key: string | null;
  /**
   * Bağlam düzelticisi uygulandıysa, bastırılan ham yorum burada korunur.
   * Şeffaflık için: kullanıcı hangi yorumun neden değiştirildiğini görebilir.
   */
  overridden_interpretation?: string | null;
  suggested_tests?: string[];
}

/** İndekslerin önerdiği ayırt edici test. */
export interface SuggestedTest {
  id: string;
  label: string;
  in_catalog: boolean;
  /** Bu testi hangi indeks(ler) önerdi. */
  reason: string;
}

/** Hibrit katmanın üretken değerlendirmesi. Katman kapalıysa `null`. */
export interface Narrative {
  text: string | null;
  model: string;
  provider: string;
  elapsed_ms: number;
  error: string | null;
}

export interface AnalyzeResponse {
  engine_version: string;
  disclaimer: string;
  processing_ms: number;
  executive_summary: string;
  /** Kural motorunun ürettiği yapılandırılmış klinik özet (modele giden metin). */
  clinical_brief?: string;
  narrative?: Narrative | null;
  physiological_metrics: { bmi: number; bmr: number; status: string };
  clinical_indices: {
    computed: ClinicalIndex[];
    /** Belirsiz örüntüyü çözecek ayırt edici testler (ör. kas mı karaciğer mi → CK). */
    suggested_tests?: SuggestedTest[];
    flagged_count: number;
    unavailable: Array<{ id: string; label: string; missing: string }>;
    basis: string;
  };
  clinical_findings: {
    primary_focus_domain: string;
    abnormal_parameters_detected: AbnormalParameter[];
    evaluated_parameter_count: number;
    skipped_parameters: string[];
    domain_load: Record<string, number>;
  };
  ai_inference_results: {
    probabilities_chart_data: DiagnosisCandidate[];
    fine_tuned_model: boolean;
    /** Yalnızca model çıkarımının süresi (toplam istek süresinden ayrı). */
    inference_ms: number;
    device: string;
    model_checkpoint: string;
    candidates_considered: number;
    prompt_token_count: number;
    probability_basis: string;
    confidence_status: string;
  };
  bio_nutritional_protocol: {
    target_active_compounds: string[];
    allergy_cleared_foods: string[];
    biochemical_synergies: string[];
    contraindicated_inhibitors: string[];
    excluded_by_allergy: string[];
    excluded_allergens_count: number;
    matched_protocols: string[];
    symptom_protocols: string[];
  };
}

/** OCR'ın hatalı okumuş olabileceği bir değer. */
export interface OcrSuspect {
  parameter: string;
  label: string;
  value: string;
  reason: "decimal_shift" | "extreme_deviation";
  /** Ondalık hatası tespit edildiyse önerilen düzeltme. */
  suggestion: string | null;
  message: string;
}

export interface UploadResponse {
  status: string;
  extracted: Record<string, string>;
  page_count: number;
  matched_count: number;
  suspects: OcrSuspect[];
  ocr_engine: string;
  notice: string;
}

export interface AnalyzeRequest {
  values: Record<string, string>;
  biometrics: { yas: number; cinsiyet: string; kilo: number; boy: number };
  medical: { kronik: string; alerjiler: string[]; genetik_riskler: string[] };
}

// ── İstekler ──────────────────────────────────────────────────────────────
class ApiError extends Error {
  constructor(message: string, readonly statusCode?: number) {
    super(message);
    this.name = "ApiError";
  }
}

/** FastAPI hem string hem de doğrulama hatası dizisi dönebilir; ikisini de metne çevirir. */
async function readErrorDetail(response: Response): Promise<string> {
  try {
    const body = await response.json();
    const detail = body?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail.map((item) => item?.msg ?? JSON.stringify(item)).join("; ");
    }
  } catch {
    // JSON değilse aşağıdaki genel mesaja düşülür
  }
  return `Sunucu ${response.status} durum kodu döndürdü.`;
}

async function request<T>(path: string, init: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, init);
  } catch {
    throw new ApiError(
      `Sunucuya bağlanılamadı (${API_BASE_URL}). api_server.py çalışıyor mu?`,
    );
  }
  if (!response.ok) {
    throw new ApiError(await readErrorDetail(response), response.status);
  }
  return (await response.json()) as T;
}

export function analyze(payload: AnalyzeRequest): Promise<AnalyzeResponse> {
  return request<AnalyzeResponse>("/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

// ── Sohbet ────────────────────────────────────────────────────────────────
export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
}

export interface ChatResponse {
  answer: string;
  model: string;
  elapsed_ms: number;
  disclaimer: string;
}

/**
 * Hastanın kendi bulguları hakkında soru sormasını sağlar.
 *
 * Sunucu durumsuzdur: `brief` her istekte gönderilir, yani sağlık verisi
 * sunucuda saklanmaz.
 */
export function chat(brief: string, question: string, history: ChatTurn[]): Promise<ChatResponse> {
  return request<ChatResponse>("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ brief, question, history }),
  });
}

export function chatSuggestions(): Promise<{ questions: string[] }> {
  return request<{ questions: string[] }>("/chat/suggestions", { method: "GET" });
}

export function uploadReport(file: File): Promise<UploadResponse> {
  const body = new FormData();
  body.append("file", file);
  // Content-Type başlığı elle EKLENMEZ; tarayıcı multipart sınırını kendisi yazar.
  return request<UploadResponse>("/upload-report", { method: "POST", body });
}

export { ApiError };

// ── Durum yoklaması ───────────────────────────────────────────────────────
export type ConnectionState = "checking" | "online" | "offline";

/**
 * Backend'i yoklar ve arayüzün çevrimdışı uyarısı gösterebilmesini sağlar.
 * `intervalMs` verilirse periyodik olarak tekrar dener.
 */
export function useBackendStatus(intervalMs = 0) {
  const [state, setState] = useState<ConnectionState>("checking");
  const [status, setStatus] = useState<BackendStatus | null>(null);

  const check = useCallback(async (signal?: AbortSignal) => {
    // Durum güncellemeleri yalnızca `await`ten SONRA yapılır; efekt gövdesinde
    // senkron setState çağrısı oluşmaz.
    try {
      const response = await fetch(`${API_BASE_URL}/status`, { signal, cache: "no-store" });
      if (!response.ok) throw new Error(String(response.status));
      const payload = (await response.json()) as BackendStatus;
      if (signal?.aborted) return;
      setStatus(payload);
      setState("online");
    } catch {
      if (signal?.aborted) return;
      setStatus(null);
      setState("offline");
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const timer = intervalMs > 0 ? setInterval(() => void check(controller.signal), intervalMs) : undefined;

    // İlk yoklama da zamanlayıcıya devredilir: böylece efekt gövdesi hiçbir
    // durum güncellemesini tetiklemez, sadece harici sistemi kurar.
    const initial = setTimeout(() => void check(controller.signal), 0);

    return () => {
      clearTimeout(initial);
      if (timer !== undefined) clearInterval(timer);
      controller.abort();
    };
  }, [check, intervalMs]);

  return { state, status, refresh: () => void check() };
}

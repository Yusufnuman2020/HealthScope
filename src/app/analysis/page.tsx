"use client";
import React, { useState } from "react";
import { ArrowLeft } from "lucide-react";

import { AnalysisForm, type FormState } from "@/components/analysis/AnalysisForm";
import { ResultCard, type PatientContext } from "@/components/analysis/ResultCard";
import { analyze, useBackendStatus, type AnalyzeResponse, API_BASE_URL } from "@/lib/api";
import { Notice, PageHeader, StatusDot } from "@/components/ui/Primitives";

export default function AnalysisPage() {
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [patient, setPatient] = useState<PatientContext | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Statik yayında (GitHub Pages) backend'e erişilemez; kullanıcıya sessiz
  // hata yerine açık bir uyarı gösterilir.
  const { state, status, refresh } = useBackendStatus(30_000);

  const handleRunAnalysis = async (formData: FormState) => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await analyze({
        values: formData.labValues,
        biometrics: {
          yas: Number(formData.biometrics.yas),
          cinsiyet: formData.biometrics.cinsiyet,
          kilo: Number(formData.biometrics.kilo),
          boy: Number(formData.biometrics.boy),
        },
        medical: {
          kronik: formData.medical.kronik || "Yok",
          alerjiler: formData.medical.alerjiler,
          genetik_riskler: formData.medical.genetik ? [formData.medical.genetik] : [],
        },
      });

      setPatient({
        age: Number(formData.biometrics.yas) || 0,
        gender: formData.biometrics.cinsiyet === "male" ? "Erkek" : "Kadın",
        allergyCount: formData.medical.alerjiler.length,
      });
      setResult(response);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (caught) {
      console.error("Analiz hatası:", caught);
      setError(caught instanceof Error ? caught.message : "Bilinmeyen bir hata oluştu.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Kan Analizi"
        subtitle="Klinik karar destek sistemi — teşhis aracı değildir"
        aside={
          <StatusDot
            state={state}
            label={state === "online" ? `Çevrimiçi · ${status?.hardware.device}` : undefined}
            onRetry={refresh}
          />
        }
      />

      {state === "offline" && (
        <Notice tone="warn" title="Analiz sunucusuna ulaşılamıyor">
          <p className="mb-2">
            Yapay zekâ çekirdeği yerel olarak çalışır ve statik yayınlanan siteden erişilemez.
            Analiz için projeyi indirip sunucuyu başlatın:
          </p>
          <code className="mb-2 block rounded-sm border border-line bg-sunken px-3 py-2 font-mono text-[11px] text-ink">
            pip install -r requirements.txt &amp;&amp; python api_server.py
          </code>
          <p className="text-[11px]">
            Beklenen adres: <span className="font-mono">{API_BASE_URL}</span> — farklıysa{" "}
            <span className="font-mono">NEXT_PUBLIC_API_URL</span> ile değiştirin.
          </p>
        </Notice>
      )}

      {status?.inference.state === "error" && (
        <Notice tone="danger" title="Yapay zekâ modeli yüklenemedi">
          {status.inference.error}
        </Notice>
      )}

      {state === "online" && status && !status.inference.fine_tuned && (
        <Notice tone="warn" title="Fine-tune edilmemiş temel model kullanılıyor">
          <span className="font-mono">HEALTHSCOPE_MODEL_PATH</span> tanımlı olmadığı için çıkarım{" "}
          <span className="font-mono">{status.inference.base_model}</span> ile yapılıyor. Dil modeli
          çıktısının klinik anlamlılığı sınırlıdır.
        </Notice>
      )}

      {error && (
        <Notice tone="danger" title="Analiz tamamlanamadı">
          {error}
        </Notice>
      )}

      {!result ? (
        <AnalysisForm
          onAnalyze={handleRunAnalysis}
          isLoading={isLoading}
          disabled={state === "offline"}
          pdfSupported={status?.pdf_support ?? false}
        />
      ) : (
        <div className="space-y-6">
          <button
            data-print-hide
            onClick={() => {
              setResult(null);
              setError(null);
            }}
            className="inline-flex items-center gap-2 rounded-md border border-line bg-raised px-3.5 py-2 text-sm font-medium text-ink-muted transition-colors hover:bg-hover hover:text-ink"
          >
            <ArrowLeft size={15} /> Yeni analiz
          </button>
          <ResultCard result={result} patient={patient} />
        </div>
      )}
    </div>
  );
}

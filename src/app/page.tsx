"use client";
import React from "react";
import { ArrowRight, Brain, Cpu, Database, FlaskConical, Stethoscope } from "lucide-react";
import Link from "next/link";

import { CATALOG_STATS } from "@/lib/catalog";
import { useBackendStatus } from "@/lib/api";
import { PageHeader, StatusDot, Panel } from "@/components/ui/Primitives";
import { PipelineDiagram } from "@/components/PipelineDiagram";

const STATE_LABEL: Record<string, string> = {
  ready: "Hazır",
  loading: "Yükleniyor",
  not_loaded: "Beklemede",
  error: "Hata",
  disabled: "Kapalı",
};

export default function DashboardPage() {
  const { state, status } = useBackendStatus(30_000);
  const online = state === "online" && status !== null;

  return (
    <div className="space-y-8">
      <PageHeader
        title="Genel Bakış"
        subtitle="Laboratuvar verilerinden klinik çıkarım ve beslenme protokolü"
        aside={<StatusDot state={state} label={online ? `Sunucu v${status.engine_version}` : undefined} />}
      />

      {/* ── Çıkarım motoru: iki model ayrı ayrı ── */}
      <Panel
        title="Çıkarım motoru"
        description="Analiz iki dil modelini farklı görevlerde kullanır"
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <ModelCard
            icon={Brain}
            name="BERTurk"
            role="Fill-mask · klinik örüntü adayları"
            detail={
              online
                ? status.inference.fine_tuned
                  ? `Fine-tuned: ${status.inference.checkpoint}`
                  : `Temel model: ${status.inference.base_model}`
                : "Sunucu başlatılmadı"
            }
            state={online ? status.inference.state : "offline"}
          />
          <ModelCard
            icon={Cpu}
            name={online && status.narrative_engine?.model ? status.narrative_engine.model : "Qwen 2.5"}
            role="Üretken · gerekçeli değerlendirme ve sohbet"
            detail={
              online
                ? status.narrative_engine?.enabled
                  ? `${status.narrative_engine.provider} · ${status.narrative_engine.precision ?? "—"}`
                  : "Devre dışı (HEALTHSCOPE_LLM_PROVIDER=none)"
                : "Sunucu başlatılmadı"
            }
            state={online ? (status.narrative_engine?.state ?? "disabled") : "offline"}
          />
        </div>

        <p className="mt-3 text-[12px] leading-relaxed text-ink-subtle">
          Donanım: {online ? status.hardware.device : "—"}
          {online && status.hardware.cuda_available && " · CUDA hızlandırma etkin"}
          {online && ` · OCR ${STATE_LABEL[status.ocr.state] ?? status.ocr.state}`}
        </p>
      </Panel>

      {/* ── Katalog metrikleri ── */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Metric icon={Database} label="Parametre kataloğu" value={String(CATALOG_STATS.parameterCount)} note={`${CATALOG_STATS.groupCount} panelde tanımlı`} />
        <Metric icon={FlaskConical} label="Klinik indeks" value={String(CATALOG_STATS.indexCount)} note="Literatür formülleriyle hesaplanır" />
        <Metric icon={Stethoscope} label="Beslenme protokolü" value={String(CATALOG_STATS.protocolCount)} note={`${CATALOG_STATS.foodCount} besin, ${CATALOG_STATS.compoundCount} bileşen`} />
        <Metric icon={Brain} label="Klinik terim" value={online ? String(status.catalog.clinical_term_count) : "—"} note="Sözlük eşleşmesi için" />
      </div>

      {/* ── Nasıl çalışır ── */}
      <Panel
        title="Uygulama nasıl çalışır?"
        description="Analiz hattı — sekiz aşama, iki dil modeli"
      >
        <PipelineDiagram />
      </Panel>

      <div className="grid gap-4 lg:grid-cols-3">
        <Panel className="lg:col-span-2">
          <h2 className="mb-3 text-base font-semibold text-ink">HealthScope nedir?</h2>
          <p className="text-sm leading-relaxed text-ink-muted">
            Kan tahlili sonuçlarını referans aralıklarıyla karşılaştırır, literatürde tanımlı
            klinik indeksleri hesaplar ve gıda mühendisliği perspektifinden beslenme protokolü
            önerir. Baskın organ sistemini belirler, alerjenleri dışlar ve bulguları kaynak
            göstererek raporlar.
          </p>
          <p className="mt-4 border-l-2 border-warn-line bg-warn-soft px-4 py-3 text-[13px] leading-relaxed text-ink-muted">
            Sistem teşhis koymaz. Üretilen çıktılar hekim değerlendirmesinin yerine geçmez.
          </p>
        </Panel>

        <Panel className="flex flex-col justify-between gap-5">
          <div>
            <h2 className="mb-2 text-base font-semibold text-ink">Analize başla</h2>
            <p className="text-sm leading-relaxed text-ink-muted">
              Değerleri elle girin ya da tahlil raporunuzu yükleyip OCR ile doldurun.
            </p>
          </div>
          <Link
            href="/analysis"
            className="inline-flex items-center justify-center gap-2 rounded-md bg-accent px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-accent-hover"
          >
            Kan analizi <ArrowRight size={16} />
          </Link>
        </Panel>
      </div>
    </div>
  );
}

const STATE_TONE: Record<string, string> = {
  ready: "bg-ok",
  loading: "bg-warn",
  not_loaded: "bg-ink-subtle",
  error: "bg-high",
  disabled: "bg-ink-subtle",
  offline: "bg-ink-subtle",
};

function ModelCard({
  icon: Icon,
  name,
  role,
  detail,
  state,
}: {
  icon: React.ComponentType<{ size?: number; className?: string }>;
  name: string;
  role: string;
  detail: string;
  state: string;
}) {
  return (
    <div className="rounded-md border border-line bg-raised p-4">
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <Icon size={15} className="shrink-0 text-ink-subtle" />
          <span className="truncate text-[13px] font-semibold text-ink" title={name}>
            {name}
          </span>
        </div>
        <span className="inline-flex shrink-0 items-center gap-1.5 text-[11px] text-ink-muted">
          <span className={`h-2 w-2 rounded-full ${STATE_TONE[state] ?? "bg-ink-subtle"}`} />
          {STATE_LABEL[state] ?? "Çevrimdışı"}
        </span>
      </div>
      <p className="text-[11px] text-ink-subtle">{role}</p>
      <p className="mt-1.5 truncate font-mono text-[11px] text-ink-muted" title={detail}>
        {detail}
      </p>
    </div>
  );
}

function Metric({
  icon: Icon,
  label,
  value,
  note,
}: {
  icon: React.ComponentType<{ size?: number; className?: string }>;
  label: string;
  value: string;
  note: string;
}) {
  return (
    <div className="rounded-lg border border-line bg-raised p-4">
      <div className="mb-2.5 flex items-center gap-2">
        <Icon size={14} className="text-ink-subtle" />
        <span className="text-[11px] font-medium text-ink-subtle">{label}</span>
      </div>
      <p className="tnum truncate text-xl font-semibold text-ink" title={value}>
        {value}
      </p>
      <p className="mt-1 truncate text-[11px] text-ink-subtle" title={note}>
        {note}
      </p>
    </div>
  );
}

"use client";
import React from "react";
import { Brain, Cpu, ScanText, Zap } from "lucide-react";

import { CATALOG_STATS } from "@/lib/catalog";
import { useBackendStatus } from "@/lib/api";
import { Badge, Notice, PageHeader, Panel, StatusDot } from "@/components/ui/Primitives";

const STATE_LABELS: Record<string, string> = {
  not_loaded: "Yüklenmedi",
  loading: "Yükleniyor",
  ready: "Hazır",
  error: "Hata",
};

export default function ModelStatusPage() {
  // Bu sayfa daha önce sabit yazılmış değerler gösteriyordu (checkpoint #8439,
  // "CUDA:0 Active", sahte log satırları). Artık her şey /status'tan gelir.
  const { state, status, refresh } = useBackendStatus(15_000);
  const online = state === "online" && status !== null;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Model Durumu"
        subtitle="Çıkarım motoru ve altyapı — canlı veri"
        aside={
          <StatusDot
            state={state}
            label={online ? `Motor v${status.engine_version}` : undefined}
            onRetry={refresh}
          />
        }
      />

      {!online && state !== "checking" && (
        <Notice tone="warn" title="Sunucuya ulaşılamıyor">
          Model metrikleri okunamıyor. Aşağıdaki katalog envanteri yerel veritabanından gelir;
          model durumu alanları sunucu açılınca dolar.
        </Notice>
      )}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Metric
          icon={Brain}
          label="Aktif model"
          value={online ? (status.inference.fine_tuned ? status.inference.checkpoint ?? "—" : status.inference.base_model) : "—"}
          note={
            online
              ? status.inference.fine_tuned
                ? "Fine-tuned checkpoint"
                : "Fine-tune edilmemiş temel model"
              : "Sunucu kapalı"
          }
        />
        <Metric
          icon={Zap}
          label="Çıkarım durumu"
          value={online ? STATE_LABELS[status.inference.state] ?? status.inference.state : "—"}
          note={online ? "Maskeleme tabanlı çıkarım hattı" : "Bilinmiyor"}
          tone={online && status.inference.state === "ready" ? "ok" : "neutral"}
        />
        <Metric
          icon={Cpu}
          label="Donanım"
          value={online ? status.hardware.device : "—"}
          note={online ? (status.hardware.cuda_available ? "CUDA kullanılabilir" : "CPU çıkarımı") : "Bilinmiyor"}
        />
        <Metric
          icon={ScanText}
          label="OCR motoru"
          value={online ? (status.ocr_support ? "EasyOCR" : "Kapalı") : "—"}
          note={online ? `TR + EN · ${STATE_LABELS[status.ocr.state] ?? status.ocr.state}` : "Bilinmiyor"}
          tone={online && status.ocr_support ? "ok" : "neutral"}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Panel title="Motor konfigürasyonu" className="lg:col-span-2">
          <dl className="grid gap-x-6 gap-y-4 sm:grid-cols-2">
            <ConfigRow label="Temel model" value={online ? status.inference.base_model : "—"} />
            <ConfigRow
              label="Checkpoint"
              value={online ? status.inference.checkpoint ?? "Tanımlı değil" : "—"}
              warn={online && !status.inference.fine_tuned}
            />
            <ConfigRow
              label="Hedef cihaz"
              value={online ? `${status.hardware.device}${status.hardware.cuda_available ? " (CUDA)" : ""}` : "—"}
            />
            <ConfigRow
              label="Klinik veritabanı"
              value={online ? (status.database_ok ? "Doğrulandı" : "Hatalı") : "—"}
              warn={online && !status.database_ok}
            />
            <ConfigRow
              label="PDF desteği"
              value={online ? (status.pdf_support ? "Etkin (Poppler)" : "Kapalı") : "—"}
              warn={online && !status.pdf_support}
            />
            <ConfigRow
              label="Yükleme sınırı"
              value={online ? `${status.limits.max_upload_mb} MB · ${status.limits.max_pdf_pages} sayfa` : "—"}
            />
          </dl>

          {online && status.inference.error && (
            <p className="mt-5 break-words rounded-md border border-high-line bg-high-soft px-4 py-3 font-mono text-[11px] text-high">
              {status.inference.error}
            </p>
          )}
        </Panel>

        <Panel title="Katalog envanteri" aside={<Badge>database.json</Badge>}>
          <dl className="space-y-2.5 text-[12px]">
            {[
              { label: "Parametre", value: CATALOG_STATS.parameterCount },
              { label: "Panel", value: CATALOG_STATS.groupCount },
              { label: "Klinik indeks", value: CATALOG_STATS.indexCount },
              { label: "Beslenme protokolü", value: CATALOG_STATS.protocolCount },
              { label: "Farklı besin", value: CATALOG_STATS.foodCount },
              { label: "Aktif bileşen", value: CATALOG_STATS.compoundCount },
              { label: "Klinik terim", value: online ? status.catalog.clinical_term_count : "—" },
            ].map((row) => (
              <div key={row.label} className="flex items-baseline justify-between gap-3 border-b border-line pb-2 last:border-0">
                <dt className="text-ink-muted">{row.label}</dt>
                <dd className="tnum font-semibold text-ink">{row.value}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-4 text-[11px] leading-relaxed text-ink-subtle">
            Bu sayılar <span className="font-mono">database.json</span> dosyasından derleme anında
            okunur; backend ile aynı kaynaktır.
          </p>
        </Panel>
      </div>
    </div>
  );
}

const METRIC_TONES = { neutral: "text-ink-subtle", ok: "text-ok" } as const;

function Metric({
  icon: Icon,
  label,
  value,
  note,
  tone = "neutral",
}: {
  icon: React.ComponentType<{ size?: number; className?: string }>;
  label: string;
  value: string;
  note: string;
  tone?: keyof typeof METRIC_TONES;
}) {
  return (
    <div className="rounded-lg border border-line bg-raised p-4">
      <div className="mb-2.5 flex items-center gap-2">
        <Icon size={14} className={METRIC_TONES[tone]} />
        <span className="text-[11px] font-medium text-ink-subtle">{label}</span>
      </div>
      <p className="truncate text-sm font-semibold text-ink" title={value}>
        {value}
      </p>
      <p className="mt-1 truncate text-[11px] text-ink-subtle" title={note}>
        {note}
      </p>
    </div>
  );
}

function ConfigRow({ label, value, warn }: { label: string; value: string; warn?: boolean }) {
  return (
    <div>
      <dt className="mb-1 text-[11px] font-medium text-ink-subtle">{label}</dt>
      <dd className={`break-words font-mono text-[13px] ${warn ? "text-warn" : "text-ink"}`}>{value}</dd>
    </div>
  );
}

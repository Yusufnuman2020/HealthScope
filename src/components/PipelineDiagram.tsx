"use client";
import React from "react";

/**
 * Analiz hattı şeması — uygulamanın nasıl çalıştığını tek bakışta anlatır.
 *
 * Sıra kasıtlıdır: deterministik katmanlar sonucu üretir, dil modelleri
 * onların ÜZERİNDE çalışır. Ham laboratuvar değerini doğrudan üretken modele
 * vermek 126 vakalık ölçümde belirgin biçimde daha kötü sonuç veriyordu.
 *
 * Aşamaların sırası `api_server.py` içindeki `/analyze` akışını birebir
 * yansıtır; hangi modelin nerede devreye girdiği açıkça yazılır çünkü
 * "yapay zeka kullanıyor" demek tek başına hiçbir şey anlatmıyor.
 */

interface Stage {
  no: string;
  title: string;
  detail: string;
  kind: "input" | "rule" | "model" | "output";
  /** Bu aşamada çalışan model — varsa rozet olarak gösterilir. */
  model?: string;
}

const STAGES: Stage[] = [
  { no: "1", title: "Veri girişi", detail: "Elle giriş veya PDF/görsel", kind: "input", model: "EasyOCR" },
  { no: "2", title: "Sapma tespiti", detail: "Cinsiyete duyarlı referans aralıkları", kind: "rule" },
  { no: "3", title: "Klinik indeksler", detail: "16 literatür formülü + bağlam düzelticileri", kind: "rule" },
  { no: "4", title: "Sistem yükü", detail: "Baskın organ sistemi ve anatomik dağılım", kind: "rule" },
  {
    no: "5",
    title: "Örüntü çıkarımı",
    detail: "Bulgu örüntüsünden olası klinik tablo sıralaması",
    kind: "model",
    model: "BERTurk",
  },
  { no: "6", title: "Klinik özet", detail: "Bulgular yapılandırılmış metne çevrilir", kind: "rule" },
  {
    no: "7",
    title: "Gerekçelendirme",
    detail: "Özet üzerinde akıl yürütüp değerlendirme yazar",
    kind: "model",
    model: "Qwen2.5-3B",
  },
  { no: "8", title: "Rapor", detail: "Bulgular, indeksler, beslenme protokolü, sohbet", kind: "output" },
];

const KIND_STYLE: Record<Stage["kind"], { box: string; dot: string; badge: string; label: string }> = {
  input: {
    box: "border-line bg-sunken",
    dot: "bg-ink-subtle",
    badge: "border-line bg-raised text-ink-muted",
    label: "Girdi",
  },
  rule: {
    box: "border-ok-line bg-ok-soft",
    dot: "bg-ok",
    badge: "border-ok-line bg-raised text-ok",
    label: "Deterministik",
  },
  model: {
    box: "border-accent-line bg-accent-soft",
    dot: "bg-accent",
    badge: "border-accent-line bg-raised text-accent",
    label: "Dil modeli",
  },
  output: {
    box: "border-line bg-raised",
    dot: "bg-ink-muted",
    badge: "border-line bg-raised text-ink-muted",
    label: "Çıktı",
  },
};

export function PipelineDiagram() {
  return (
    <div>
      <ol className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {STAGES.map((stage) => {
          const style = KIND_STYLE[stage.kind];
          return (
            <li key={stage.no} className={`relative rounded-md border p-3 ${style.box}`}>
              <div className="mb-1.5 flex items-center gap-2">
                <span
                  className={`inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[9px] font-bold text-white ${style.dot}`}
                >
                  {stage.no}
                </span>
                <span className="text-[13px] font-semibold text-ink">{stage.title}</span>
              </div>
              <p className="text-[11px] leading-relaxed text-ink-muted">{stage.detail}</p>
              {stage.model && (
                <span
                  className={`mt-2 inline-block rounded border px-1.5 py-0.5 text-[10px] font-medium ${style.badge}`}
                >
                  {stage.model}
                </span>
              )}
            </li>
          );
        })}
      </ol>

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[11px] text-ink-subtle">
        {(Object.keys(KIND_STYLE) as Stage["kind"][]).map((kind) => (
          <span key={kind} className="inline-flex items-center gap-1.5">
            <span className={`inline-block h-2 w-2 rounded-full ${KIND_STYLE[kind].dot}`} />
            {KIND_STYLE[kind].label}
          </span>
        ))}
      </div>

      <p className="mt-4 border-l-2 border-accent-line bg-accent-soft px-4 py-3 text-[12px] leading-relaxed text-ink-muted">
        <strong className="font-semibold text-ink">İki model, iki ayrı iş:</strong>{" "}
        <strong className="font-semibold text-ink">BERTurk</strong> bulgu örüntüsünden olası klinik
        tabloları sıralar; <strong className="font-semibold text-ink">Qwen2.5-3B</strong> ise
        teşhis koymaz, kural motorunun ürettiği klinik özeti gerekçelendirip anlaşılır dile çevirir.
        Ham laboratuvar değeri doğrudan üretken modele verildiğinde isabet %65&apos;te kalıyordu;
        kural motorunun çıkardığı klinik öznitelikler verildiğinde %94&apos;e çıkıyor — akıl
        yürütmenin yarısı zaten yapılmış oluyor.
      </p>
    </div>
  );
}

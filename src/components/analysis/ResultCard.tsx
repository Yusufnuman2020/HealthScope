"use client";
import React, { useMemo } from "react";
import {
  Bar, BarChart, Cell, PolarAngleAxis, PolarGrid, PolarRadiusAxis, Radar, RadarChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { Ban, ChevronRight, FlaskConical, Printer, Utensils } from "lucide-react";

import type { AnalyzeResponse, ClinicalIndex } from "@/lib/api";
import { Badge, Notice, Panel } from "@/components/ui/Primitives";
import { ChatPanel } from "@/components/analysis/ChatPanel";
import { AnatomyMap } from "@/components/analysis/AnatomyMap";

/** Sunucu yanıtında olmayan, forma özgü hasta bilgileri. */
export interface PatientContext {
  age: number;
  gender: string;
  allergyCount: number;
}

interface ResultCardProps {
  result: AnalyzeResponse;
  patient: PatientContext | null;
}

/** Grafik renkleri tema değişkenlerinden okunur — recharts CSS sınıfı alamaz. */
function cssVar(name: string, fallback: string) {
  if (typeof window === "undefined") return fallback;
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;
}

const truncate = (value: string, limit = 30) =>
  value.length > limit ? `${value.slice(0, limit - 1)}…` : value;

interface DiagnosisDatum {
  name: string;
  fullName: string;
  probability: number;
  modelScore: number;
}

interface DeviationDatum {
  name: string;
  label: string;
  deviation: number;
  status: "Yüksek" | "Düşük";
  value: number;
  unit: string;
  reference: string;
}

interface DomainDatum {
  domain: string;
  load: number;
  raw: number;
}

const INDEX_TONES: Record<ClinicalIndex["level"], { badge: Parameters<typeof Badge>[0]["tone"]; value: string; label: string }> = {
  critical: { badge: "high", value: "text-high", label: "Kritik" },
  high: { badge: "high", value: "text-high", label: "Yüksek" },
  borderline: { badge: "warn", value: "text-warn", label: "Sınırda" },
  normal: { badge: "ok", value: "text-ok", label: "Normal" },
};

export const ResultCard = ({ result, patient }: ResultCardProps) => {
  const findings = result.clinical_findings.abnormal_parameters_detected;
  const inference = result.ai_inference_results;
  const diagnoses = inference.probabilities_chart_data;
  const indices = result.clinical_indices ?? {
    computed: [], flagged_count: 0, unavailable: [], basis: "", suggested_tests: [],
  };
  const protocol = result.bio_nutritional_protocol;
  const metrics = result.physiological_metrics;

  const colors = useMemo(
    () => ({
      high: cssVar("--high", "#b03024"),
      low: cssVar("--low", "#16558f"),
      accent: cssVar("--accent", "#14618f"),
      muted: cssVar("--text-subtle", "#8a94a2"),
      grid: cssVar("--chart-grid", "#e4e8ee"),
      axis: cssVar("--chart-axis", "#8a94a2"),
    }),
    [],
  );

  const deviationData = useMemo<DeviationDatum[]>(
    () =>
      findings.slice(0, 12).map((finding) => ({
        name: finding.parameter,
        label: finding.label,
        deviation: finding.deviation_percentage,
        status: finding.status,
        value: finding.value,
        unit: finding.unit,
        reference: finding.reference,
      })),
    [findings],
  );

  const diagnosisData = useMemo<DiagnosisDatum[]>(
    () =>
      diagnoses.map((item) => ({
        name: truncate(item.diagnosis),
        fullName: item.diagnosis,
        probability: item.probability,
        modelScore: item.model_score,
      })),
    [diagnoses],
  );

  const domainData = useMemo<DomainDatum[]>(() => {
    const entries = Object.entries(result.clinical_findings.domain_load);
    const max = Math.max(...entries.map(([, load]) => load), 1);
    return entries.map(([domain, load]) => ({
      domain,
      load: Math.round((load / max) * 100),
      raw: Math.round(load),
    }));
  }, [result.clinical_findings.domain_load]);

  return (
    <div className="space-y-5">
      {/* ── FERAGAT ── */}
      <Notice tone="warn">{result.disclaimer}</Notice>

      {/* ── HASTA KÜNYESİ ── */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        {[
          { label: "Yaş", value: patient?.age ?? "-" },
          { label: "Cinsiyet", value: patient?.gender ?? "-" },
          { label: "VKİ", value: metrics.bmi, note: metrics.status },
          { label: "Bazal metabolizma", value: `${metrics.bmr} kcal` },
          { label: "Alerji kaydı", value: `${patient?.allergyCount ?? 0} adet` },
        ].map((stat) => (
          <div key={stat.label} className="rounded-lg border border-line bg-raised p-3.5">
            <p className="text-[11px] text-ink-subtle">{stat.label}</p>
            <p className="tnum mt-0.5 text-lg font-semibold text-ink">{stat.value}</p>
            {stat.note && <p className="mt-0.5 text-[10px] leading-tight text-ink-subtle">{stat.note}</p>}
          </div>
        ))}
      </div>

      {/* ── ÖZET ── */}
      <Panel
        title="Klinik değerlendirme"
        description={`Baskın alan: ${result.clinical_findings.primary_focus_domain}`}
        aside={
          <button
            data-print-hide
            onClick={() => window.print()}
            className="inline-flex items-center gap-1.5 rounded-md border border-line px-3 py-1.5 text-xs font-medium text-ink-muted transition-colors hover:bg-hover hover:text-ink"
          >
            <Printer size={13} /> Yazdır / PDF
          </button>
        }
      >
        <p className="text-sm leading-relaxed text-ink">{result.executive_summary}</p>
        <p className="mt-3 text-xs text-ink-subtle">
          {result.clinical_findings.evaluated_parameter_count} parametre değerlendirildi,{" "}
          {findings.length} tanesi referans dışı. İşlem süresi {result.processing_ms} ms.
          {result.clinical_findings.skipped_parameters.length > 0 &&
            ` Tanınmayan ${result.clinical_findings.skipped_parameters.length} alan atlandı: ${result.clinical_findings.skipped_parameters.join(", ")}.`}
        </p>
      </Panel>

      {/* ── HİBRİT DEĞERLENDİRME ──
          Kural motorunun çıkardığı öznitelikler üzerinde akıl yürüten üretken
          model. Katman kapalıysa bu bölüm hiç görünmez. */}
      {result.narrative?.text && (
        <Panel
          title="Gerekçeli değerlendirme"
          description={`${result.narrative.model} · ${result.narrative.provider} · ${result.narrative.elapsed_ms} ms`}
          aside={<Badge tone="accent">Hibrit katman</Badge>}
        >
          <div className="space-y-2 whitespace-pre-line text-sm leading-relaxed text-ink">
            {result.narrative.text}
          </div>

          {result.clinical_brief && (
            <details className="group mt-4 border-t border-line pt-3">
              <summary className="flex cursor-pointer list-none items-center gap-1 text-[11px] text-ink-subtle hover:text-ink-muted">
                <ChevronRight size={11} className="transition-transform group-open:rotate-90" />
                Modele verilen yapılandırılmış bulgular
              </summary>
              <pre className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap rounded-md border border-line bg-sunken p-3 font-mono text-[10px] leading-relaxed text-ink-muted">
                {result.clinical_brief}
              </pre>
            </details>
          )}
        </Panel>
      )}

      {/* Sohbet: yalnızca üretken katman çalıştıysa ve klinik özet varsa.
          Bulgular her soruda sunucuya yeniden gönderilir (durumsuz). */}
      {result.narrative?.text && result.clinical_brief && (
        <ChatPanel brief={result.clinical_brief} modelLabel={result.narrative.model} />
      )}

      {result.narrative?.error && (
        <Notice tone="warn" title="Gerekçeli değerlendirme üretilemedi">
          {result.narrative.error} — kural motorunun sonuçları aşağıda değişmeden geçerlidir.
        </Notice>
      )}

      {/* ── ANATOMİK DAĞILIM ── */}
      {findings.length > 0 && <AnatomyMap findings={findings} />}

      {/* ── KLİNİK İNDEKSLER ── */}
      {indices.computed.length > 0 && (
        <Panel
          title="Klinik indeksler"
          description="Literatür formülleriyle hesaplanır — dil modelinden bağımsızdır"
          aside={<Badge tone={indices.flagged_count ? "warn" : "ok"}>{indices.flagged_count} / {indices.computed.length} dikkat çekici</Badge>}
        >
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {indices.computed.map((index) => {
              const tone = INDEX_TONES[index.level];
              return (
                <article key={index.id} className="rounded-md border border-line bg-sunken p-4">
                  <div className="mb-1 flex items-baseline justify-between gap-2">
                    <h3 className="text-[13px] font-semibold text-ink">{index.label}</h3>
                    <span className={`tnum text-base font-semibold ${tone.value}`}>
                      {index.value}
                      {index.unit && <span className="ml-1 text-[10px] text-ink-subtle">{index.unit}</span>}
                    </span>
                  </div>
                  <p className="mb-2.5 text-[11px] text-ink-subtle">{index.full_name}</p>
                  <p className="text-[12px] leading-relaxed text-ink-muted">{index.interpretation}</p>

                  {/* Bağlam düzelticisi uygulandıysa bastırılan yorum şeffaflık için gösterilir */}
                  {index.overridden_interpretation && (
                    <div className="mt-2.5 border-l-2 border-line pl-2.5">
                      <p className="text-[10px] font-medium text-ink-subtle">
                        Bağlam olmadan şöyle yorumlanırdı
                      </p>
                      <p className="text-[11px] text-ink-subtle line-through">
                        {index.overridden_interpretation}
                      </p>
                    </div>
                  )}

                  {index.suggested_tests && index.suggested_tests.length > 0 && (
                    <p className="mt-2.5 flex items-start gap-1.5 text-[11px] text-accent">
                      <FlaskConical size={11} className="mt-0.5 shrink-0" />
                      Ayırt edici test: {index.suggested_tests.join(", ")}
                    </p>
                  )}

                  <details className="group mt-3">
                    <summary className="flex cursor-pointer list-none items-center gap-1 text-[10px] text-ink-subtle hover:text-ink-muted">
                      <ChevronRight size={10} className="transition-transform group-open:rotate-90" />
                      Formül ve kaynak
                    </summary>
                    <div className="mt-2 space-y-1 border-l border-line pl-2.5">
                      <p className="break-words font-mono text-[10px] text-ink-muted">{index.formula}</p>
                      <p className="tnum text-[10px] text-ink-subtle">
                        {Object.entries(index.inputs)
                          .map(([key, value]) => `${key.toUpperCase()} = ${value}`)
                          .join("   ·   ")}
                      </p>
                      <p className="text-[10px] italic text-ink-subtle">{index.reference}</p>
                    </div>
                  </details>
                </article>
              );
            })}
          </div>

          {/* Ayırt edici test önerileri — kural motorunun en değerli çıktısı */}
          {indices.suggested_tests && indices.suggested_tests.length > 0 && (
            <div className="mt-5 border-t border-line pt-4">
              <h3 className="mb-2.5 flex items-center gap-1.5 text-xs font-semibold text-accent">
                <FlaskConical size={13} /> Önerilen ayırt edici testler
              </h3>
              <div className="space-y-1.5">
                {indices.suggested_tests.map((test) => (
                  <div
                    key={test.id}
                    className="flex flex-wrap items-baseline gap-x-2 rounded-md border border-accent-line bg-accent-soft px-3.5 py-2 text-[12px]"
                  >
                    <span className="font-semibold text-ink">{test.label}</span>
                    <span className="text-ink-muted">— {test.reason} bulgusunu netleştirir</span>
                    {!test.in_catalog && <span className="text-[10px] text-ink-subtle">(bu panelde yok)</span>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {indices.unavailable.length > 0 && (
            <p className="mt-4 border-t border-line pt-3 text-[11px] text-ink-subtle">
              Hesaplanamayan {indices.unavailable.length} indeks:{" "}
              {indices.unavailable.map((item) => `${item.label} (${item.missing} eksik)`).join(", ")}
            </p>
          )}
        </Panel>
      )}

      {/* ── BULGU TABLOSU ── */}
      <Panel title="Referans dışı parametreler" aside={<Badge tone={findings.length ? "high" : "ok"}>{findings.length} bulgu</Badge>}>
        {findings.length === 0 ? (
          <p className="text-sm text-ok">Girilen tüm parametreler referans aralığındadır.</p>
        ) : (
          <div className="-mx-5 overflow-x-auto">
            <table className="w-full min-w-[520px] text-left text-[13px]">
              <thead>
                <tr className="border-b border-line text-[11px] font-medium text-ink-subtle">
                  <th className="px-5 py-2">Parametre</th>
                  <th className="px-3 py-2">Ölçüm</th>
                  <th className="px-3 py-2">Referans</th>
                  <th className="px-5 py-2 text-right">Sapma</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {findings.map((finding) => (
                  <tr key={finding.parameter} className="hover:bg-hover">
                    <td className="px-5 py-2.5">
                      <span className="text-ink">{finding.label}</span>
                      <span className="block text-[10px] text-ink-subtle">{finding.domain}</span>
                    </td>
                    <td className="tnum px-3 py-2.5 font-medium text-ink">
                      {finding.value} <span className="text-[11px] text-ink-subtle">{finding.unit}</span>
                    </td>
                    <td className="tnum px-3 py-2.5 text-ink-subtle">{finding.reference}</td>
                    <td className="px-5 py-2.5 text-right">
                      <span
                        className={`tnum font-semibold ${finding.status === "Yüksek" ? "text-high" : "text-low"}`}
                      >
                        {finding.status === "Yüksek" ? "▲" : "▼"} %{finding.deviation_percentage}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {/* ── GRAFİKLER ── */}
      {deviationData.length > 0 && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Panel
            title="Sapma şiddeti"
            aside={
              <span className="flex items-center gap-3 text-[10px] text-ink-muted">
                <span className="flex items-center gap-1">
                  <span className="h-2 w-2 rounded-xs" style={{ background: colors.high }} /> Yüksek
                </span>
                <span className="flex items-center gap-1">
                  <span className="h-2 w-2 rounded-xs" style={{ background: colors.low }} /> Düşük
                </span>
              </span>
            }
          >
            <ResponsiveContainer width="100%" height={Math.max(200, deviationData.length * 28)}>
              <BarChart data={deviationData} layout="vertical" margin={{ left: 4, right: 28, top: 4, bottom: 4 }}>
                <XAxis type="number" tick={{ fill: colors.axis, fontSize: 10 }} axisLine={false} tickLine={false} unit="%" />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={104}
                  tick={{ fill: colors.axis, fontSize: 10 }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip cursor={{ fill: "rgba(128,128,128,0.06)" }} content={<DeviationTooltip />} />
                <Bar dataKey="deviation" radius={[0, 3, 3, 0]} barSize={13}>
                  {deviationData.map((entry) => (
                    <Cell key={entry.name} fill={entry.status === "Yüksek" ? colors.high : colors.low} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            {findings.length > deviationData.length && (
              <p className="mt-2 text-[11px] text-ink-subtle">
                En yüksek sapmalı {deviationData.length} parametre gösteriliyor ({findings.length} toplam).
              </p>
            )}
          </Panel>

          {domainData.length >= 3 && (
            <Panel title="Sistem bazlı yük dağılımı">
              <ResponsiveContainer width="100%" height={260}>
                <RadarChart data={domainData} outerRadius="70%">
                  <PolarGrid stroke={colors.grid} />
                  <PolarAngleAxis dataKey="domain" tick={{ fill: colors.axis, fontSize: 10 }} />
                  <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
                  <Tooltip content={<DomainTooltip />} />
                  <Radar dataKey="load" stroke={colors.accent} fill={colors.accent} fillOpacity={0.2} />
                </RadarChart>
              </ResponsiveContainer>
              <p className="mt-1 text-[11px] text-ink-subtle">
                Her sistemdeki toplam sapma yüzdesinin en yüklü sisteme oranı.
              </p>
            </Panel>
          )}
        </div>
      )}

      {/* ── DİL MODELİ ── */}
      <Panel
        title="Dil modeli çıkarımı"
        description={`${inference.model_checkpoint} · ${inference.device} · ${inference.inference_ms} ms`}
        aside={
          <Badge tone={diagnoses[0]?.model_score >= 5 ? "neutral" : "warn"}>
            {inference.confidence_status}
          </Badge>
        }
      >
        <div className="grid gap-5 lg:grid-cols-2">
          <div>
            <ResponsiveContainer width="100%" height={Math.max(140, diagnosisData.length * 42)}>
              <BarChart data={diagnosisData} layout="vertical" margin={{ left: 4, right: 28, top: 4, bottom: 4 }}>
                <XAxis type="number" domain={[0, 100]} hide />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={150}
                  tick={{ fill: colors.axis, fontSize: 10 }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip cursor={{ fill: "rgba(128,128,128,0.06)" }} content={<DiagnosisTooltip />} />
                <Bar dataKey="probability" radius={[0, 3, 3, 0]} barSize={12}>
                  {diagnosisData.map((entry, index) => (
                    <Cell key={entry.name} fill={index === 0 ? colors.accent : colors.muted} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          <dl className="grid grid-cols-2 gap-x-4 gap-y-3 self-start text-[11px]">
            {[
              { k: "Model", v: inference.model_checkpoint },
              { k: "Cihaz", v: inference.device },
              { k: "Çıkarım süresi", v: `${inference.inference_ms} ms` },
              { k: "Prompt uzunluğu", v: `${inference.prompt_token_count} token` },
              { k: "Değerlendirilen aday", v: `${inference.candidates_considered} token` },
              { k: "Sinyal gücü", v: `%${diagnoses[0]?.model_score ?? 0} ham` },
            ].map((row) => (
              <div key={row.k} className="min-w-0">
                <dt className="text-ink-subtle">{row.k}</dt>
                <dd className="tnum truncate text-ink" title={String(row.v)}>
                  {row.v}
                </dd>
              </div>
            ))}
          </dl>
        </div>
        <p className="mt-4 border-t border-line pt-3 text-[11px] leading-relaxed text-ink-subtle">
          {inference.probability_basis}
        </p>
      </Panel>

      {/* ── BESLENME PROTOKOLÜ ── */}
      <Panel
        title="Biyo-nutrisyonel protokol"
        aside={
          <Badge>
            {protocol.matched_protocols.length} protokol
            {protocol.symptom_protocols.length > 0 && ` (${protocol.symptom_protocols.length} öyküden)`}
          </Badge>
        }
      >
        <div className="space-y-5">
          {protocol.allergy_cleared_foods.length === 0 ? (
            <p className="text-sm text-ink-muted">
              Referans dışı parametrelere bağlı spesifik bir besin protokolü tetiklenmedi.
            </p>
          ) : (
            <ChipSection title="Önerilen besinler" tone="ok" items={protocol.allergy_cleared_foods} icon={Utensils} />
          )}

          {protocol.target_active_compounds.length > 0 && (
            <ChipSection title="Hedef aktif bileşenler" tone="accent" items={protocol.target_active_compounds} />
          )}

          {protocol.contraindicated_inhibitors.length > 0 && (
            <ChipSection title="Kaçınılması önerilenler" tone="high" items={protocol.contraindicated_inhibitors} icon={Ban} />
          )}

          {protocol.excluded_by_allergy.length > 0 && (
            <div className="rounded-md border border-warn-line bg-warn-soft px-4 py-3">
              <p className="text-[11px] font-medium text-warn">Alerji nedeniyle çıkarılanlar</p>
              <p className="mt-1 text-[12px] text-ink-muted">{protocol.excluded_by_allergy.join(", ")}</p>
            </div>
          )}

          {protocol.biochemical_synergies.length > 0 && (
            <div>
              <p className="mb-2 text-[11px] font-medium text-ink-muted">Biyokimyasal sinerjiler</p>
              <ul className="space-y-1.5">
                {protocol.biochemical_synergies.map((synergy) => (
                  <li key={synergy} className="border-l-2 border-ok-line pl-3 text-[12px] leading-relaxed text-ink-muted">
                    {synergy}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </Panel>
    </div>
  );
};

// ── Grafik ipuçları ───────────────────────────────────────────────────────
const TOOLTIP_CLASS =
  "rounded-md border border-line bg-raised px-3 py-2 text-[11px] leading-relaxed text-ink shadow-sm max-w-[280px]";

interface InjectedTooltip<T> {
  active?: boolean;
  payload?: Array<{ payload: T }>;
}

function DiagnosisTooltip({ active, payload }: InjectedTooltip<DiagnosisDatum>) {
  const datum = active ? payload?.[0]?.payload : undefined;
  if (!datum) return null;
  return (
    <div className={TOOLTIP_CLASS}>
      <p className="font-semibold">{datum.fullName}</p>
      <p className="tnum text-accent">Göreli olasılık: %{datum.probability}</p>
      <p className="tnum text-ink-subtle">Ham model skoru: %{datum.modelScore}</p>
    </div>
  );
}

function DeviationTooltip({ active, payload }: InjectedTooltip<DeviationDatum>) {
  const datum = active ? payload?.[0]?.payload : undefined;
  if (!datum) return null;
  return (
    <div className={TOOLTIP_CLASS}>
      <p className="font-semibold">{datum.label}</p>
      <p className={`tnum ${datum.status === "Yüksek" ? "text-high" : "text-low"}`}>
        %{datum.deviation} {datum.status}
      </p>
      <p className="tnum text-ink-muted">
        Ölçüm: {datum.value} {datum.unit}
      </p>
      <p className="tnum text-ink-subtle">Referans: {datum.reference}</p>
    </div>
  );
}

function DomainTooltip({ active, payload }: InjectedTooltip<DomainDatum>) {
  const datum = active ? payload?.[0]?.payload : undefined;
  if (!datum) return null;
  return (
    <div className={TOOLTIP_CLASS}>
      <p className="font-semibold">{datum.domain}</p>
      <p className="tnum text-accent">Göreli yük: %{datum.load}</p>
      <p className="tnum text-ink-subtle">Toplam sapma: %{datum.raw}</p>
    </div>
  );
}

const CHIP_TONES = {
  ok: "border-ok-line bg-ok-soft text-ok",
  accent: "border-accent-line bg-accent-soft text-accent",
  high: "border-high-line bg-high-soft text-high",
} as const;

function ChipSection({
  title,
  tone,
  items,
  icon: Icon,
}: {
  title: string;
  tone: keyof typeof CHIP_TONES;
  items: string[];
  icon?: React.ComponentType<{ size?: number; className?: string }>;
}) {
  return (
    <div>
      <p className="mb-2 flex items-center gap-1.5 text-[11px] font-medium text-ink-muted">
        {Icon && <Icon size={12} />}
        {title}
      </p>
      <div className="flex flex-wrap gap-1.5">
        {items.map((item) => (
          <span
            key={item}
            className={`rounded-sm border px-2 py-1 text-[11px] font-medium ${CHIP_TONES[tone]}`}
          >
            {item}
          </span>
        ))}
      </div>
    </div>
  );
}

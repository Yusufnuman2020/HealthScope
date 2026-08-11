"use client";
import React, { useMemo, useState } from "react";

import type { AbnormalParameter } from "@/lib/api";
import {
  mapFindingsToOrgans,
  SEVERITY_FILL,
  SEVERITY_LABEL,
  type OrganId,
  type OrganState,
} from "@/lib/anatomy";
import { Panel } from "@/components/ui/Primitives";
import { AnatomyFigure } from "@/components/analysis/AnatomyFigure";

interface AnatomyMapProps {
  findings: AbnormalParameter[];
}

/**
 * Anatomik şema — bulgulara göre organları renklendirir ve canlandırır.
 *
 * Neden SVG (3B değil): bağımlılık yok, statik export'ta sorunsuz, yazdırılan
 * rapora basılır ve klinik diyagram estetiğini korur. Organ/alan eşlemesi
 * `lib/anatomy.ts` içinde ayrı tutuldu; 3B'ye geçilirse yalnızca bu dosya
 * değişir.
 */
export function AnatomyMap({ findings }: AnatomyMapProps) {
  const states = useMemo(() => mapFindingsToOrgans(findings), [findings]);
  const byId = useMemo(
    () => Object.fromEntries(states.map((s) => [s.organ.id, s])) as Record<OrganId, OrganState>,
    [states],
  );
  const [selected, setSelected] = useState<OrganId | null>(null);

  const affected = states
    .filter((s) => s.severity !== "normal")
    .sort((a, b) => b.intensity - a.intensity);

  const active = selected ? byId[selected] : affected[0] ?? null;

  const fill = (id: OrganId) => SEVERITY_FILL[byId[id]?.severity ?? "normal"];

  return (
    <Panel
      title="Anatomik dağılım"
      description="Bulguların etkilediği organ sistemleri — organa tıklayarak ayrıntıyı görün"
    >
      <div className="grid gap-5 md:grid-cols-[minmax(0,260px)_1fr]">
        <figure className="m-0">
          <AnatomyFigure
            fillOf={fill}
            isSelected={(id) => selected === id}
            onSelect={(id) => setSelected(selected === id ? null : id)}
            vesselAffected={byId.damar?.severity !== "normal"}
          />

          <figcaption className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[11px] text-ink-subtle">
            {(["normal", "hafif", "orta", "agir"] as const).map((level) => (
              <span key={level} className="inline-flex items-center gap-1.5">
                <span
                  className="inline-block h-2.5 w-2.5 rounded-[3px] border border-line"
                  style={{ background: SEVERITY_FILL[level] }}
                />
                {SEVERITY_LABEL[level]}
              </span>
            ))}
          </figcaption>
        </figure>

        {/* ── Yan panel: seçilen organın bulguları ── */}
        <div className="min-w-0">
          {affected.length === 0 ? (
            <p className="text-sm leading-relaxed text-ink-muted">
              Referans dışı bulgu bulunmadığı için hiçbir organ sistemi işaretlenmedi.
            </p>
          ) : (
            <>
              <div className="mb-3 flex flex-wrap gap-1.5">
                {affected.map((state) => (
                  <button
                    key={state.organ.id}
                    type="button"
                    onClick={() =>
                      setSelected(selected === state.organ.id ? null : state.organ.id)
                    }
                    className={`rounded-full border px-2.5 py-1 text-[11px] transition-colors ${
                      active?.organ.id === state.organ.id
                        ? "border-accent text-accent"
                        : "border-line text-ink-muted hover:border-accent"
                    }`}
                  >
                    <span
                      className="mr-1.5 inline-block h-2 w-2 rounded-full align-middle"
                      style={{ background: SEVERITY_FILL[state.severity] }}
                    />
                    {state.organ.label}
                  </button>
                ))}
              </div>

              {active && (
                <div className="rounded-md border border-line bg-sunken p-3.5">
                  <p className="mb-1 text-sm font-semibold text-ink">{active.organ.label}</p>
                  <p className="mb-3 text-[12px] text-ink-subtle">
                    {SEVERITY_LABEL[active.severity]} · {active.findings.length} bulgu
                  </p>
                  <ul className="space-y-1.5">
                    {active.findings
                      .slice()
                      .sort((a, b) => b.deviation_percentage - a.deviation_percentage)
                      .map((finding) => (
                        <li
                          key={finding.parameter}
                          className="flex items-baseline justify-between gap-3 text-[12px]"
                        >
                          <span className="min-w-0 truncate text-ink-muted">{finding.label}</span>
                          <span className="tnum shrink-0 text-ink">
                            {finding.value} {finding.unit}{" "}
                            <span className={finding.status === "Yüksek" ? "text-high" : "text-low"}>
                              {finding.status === "Yüksek" ? "▲" : "▼"}
                            </span>
                          </span>
                        </li>
                      ))}
                  </ul>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </Panel>
  );
}

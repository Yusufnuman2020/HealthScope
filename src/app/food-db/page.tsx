"use client";
import React, { useMemo, useState } from "react";
import { Ban, FlaskConical, Search, Sparkles, Utensils } from "lucide-react";

import { CATALOG_STATS, PROTOCOLS, parametersForProtocol, type NutritionProtocol } from "@/lib/catalog";
import { Badge, PageHeader, Panel } from "@/components/ui/Primitives";

/**
 * Veri doğrudan `database.json` içindeki BIO_NUTRITION_DB'den gelir — yani
 * analiz motorunun gerçekten kullandığı protokollerin ta kendisidir.
 */
interface ProtocolView extends NutritionProtocol {
  triggers: Array<{ parameterLabel: string; parameterShort: string; direction: "Yüksek" | "Düşük"; domain: string }>;
  domains: string[];
}

const PROTOCOL_VIEWS: ProtocolView[] = PROTOCOLS.map((protocol) => {
  const matches = parametersForProtocol(protocol.key);
  // Başlıkta protokol anahtarının ait olduğu parametre öne alınır.
  const primaryIndex = matches.findIndex(({ parameter }) => protocol.key.startsWith(parameter.id));
  const ordered =
    primaryIndex > 0
      ? [matches[primaryIndex], ...matches.filter((_, index) => index !== primaryIndex)]
      : matches;

  return {
    ...protocol,
    triggers: ordered.map(({ parameter, direction }) => ({
      parameterLabel: parameter.label,
      parameterShort: parameter.short,
      direction,
      domain: parameter.domain,
    })),
    domains: Array.from(new Set(matches.map(({ parameter }) => parameter.domain))),
  };
}).sort((a, b) => b.triggers.length - a.triggers.length);

const ALL_DOMAINS = Array.from(new Set(PROTOCOL_VIEWS.flatMap((p) => p.domains))).sort();

export default function FoodDatabasePage() {
  const [search, setSearch] = useState("");
  const [domainFilter, setDomainFilter] = useState<string | null>(null);

  const filtered = useMemo(() => {
    const needle = search.trim().toLocaleLowerCase("tr");
    return PROTOCOL_VIEWS.filter((protocol) => {
      if (domainFilter && !protocol.domains.includes(domainFilter)) return false;
      if (!needle) return true;
      return [
        protocol.key,
        ...protocol.foods,
        ...protocol.compounds,
        ...protocol.triggers.map((t) => `${t.parameterLabel} ${t.parameterShort}`),
      ]
        .join(" ")
        .toLocaleLowerCase("tr")
        .includes(needle);
    });
  }, [search, domainFilter]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Besin Protokolleri"
        subtitle={`${CATALOG_STATS.protocolCount} protokol · ${CATALOG_STATS.foodCount} besin · ${CATALOG_STATS.compoundCount} aktif bileşen`}
      />

      <div className="flex flex-col gap-3">
        <div className="relative max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-subtle" size={14} />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Besin, bileşen veya parametre ara (HGB, ferritin, ceviz)..."
            className="w-full rounded-md border border-line bg-raised py-2 pl-9 pr-3 text-sm text-ink outline-none transition-colors placeholder:text-ink-subtle focus:border-accent"
          />
        </div>

        <div className="flex flex-wrap gap-1.5">
          <FilterChip active={domainFilter === null} onClick={() => setDomainFilter(null)}>
            Tümü ({PROTOCOL_VIEWS.length})
          </FilterChip>
          {ALL_DOMAINS.map((domain) => (
            <FilterChip
              key={domain}
              active={domainFilter === domain}
              onClick={() => setDomainFilter(domainFilter === domain ? null : domain)}
            >
              {domain}
            </FilterChip>
          ))}
        </div>
      </div>

      <div className="grid gap-3 lg:grid-cols-2 xl:grid-cols-3">
        {filtered.map((protocol) => (
          <ProtocolCard key={protocol.key} protocol={protocol} />
        ))}
      </div>

      {filtered.length === 0 && (
        <Panel className="py-12 text-center">
          <p className="text-sm text-ink-subtle">Kriterlere uygun protokol bulunamadı.</p>
        </Panel>
      )}
    </div>
  );
}

function ProtocolCard({ protocol }: { protocol: ProtocolView }) {
  return (
    <article className="flex flex-col gap-4 rounded-lg border border-line bg-raised p-4">
      <header className="space-y-2">
        <div className="flex items-start justify-between gap-2">
          <h2 className="text-[13px] font-semibold leading-snug text-ink">
            {protocol.triggers[0]
              ? `${protocol.triggers[0].parameterLabel} — ${protocol.triggers[0].direction}`
              : protocol.key}
          </h2>
          <code className="shrink-0 rounded-sm bg-sunken px-1.5 py-0.5 font-mono text-[10px] text-ink-subtle">
            {protocol.key}
          </code>
        </div>
        <div className="flex flex-wrap gap-1">
          {protocol.triggers.map((trigger) => (
            <Badge
              key={`${trigger.parameterShort}-${trigger.direction}`}
              tone={trigger.direction === "Yüksek" ? "high" : "low"}
            >
              <span title={`${trigger.parameterLabel} (${trigger.domain})`}>
                {trigger.parameterShort} {trigger.direction === "Yüksek" ? "▲" : "▼"}
              </span>
            </Badge>
          ))}
        </div>
      </header>

      <Section icon={Utensils} title="Önerilen besinler">
        <div className="flex flex-wrap gap-1">
          {protocol.foods.map((food) => (
            <span
              key={food}
              className="rounded-sm border border-ok-line bg-ok-soft px-1.5 py-0.5 text-[11px] text-ok"
            >
              {food}
            </span>
          ))}
        </div>
      </Section>

      <Section icon={FlaskConical} title="Aktif bileşenler">
        <p className="text-[11px] leading-relaxed text-ink-muted">{protocol.compounds.join(" · ")}</p>
      </Section>

      <Section icon={Sparkles} title="Biyokimyasal sinerji">
        <p className="text-[11px] leading-relaxed text-ink-muted">{protocol.synergy}</p>
      </Section>

      <Section icon={Ban} title="Kaçınılması önerilenler">
        <p className="text-[11px] leading-relaxed text-ink-subtle">{protocol.inhibitors.join(" · ")}</p>
      </Section>

      <footer className="border-t border-line pt-2.5 text-[10px] text-ink-subtle">
        {protocol.domains.join(", ") || "Sistem bağımsız"}
      </footer>
    </article>
  );
}

function Section({
  icon: Icon,
  title,
  children,
}: {
  icon: React.ComponentType<{ size?: number; className?: string }>;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-1.5">
      <h3 className="flex items-center gap-1.5 text-[11px] font-medium text-ink-muted">
        <Icon size={11} /> {title}
      </h3>
      {children}
    </section>
  );
}

function FilterChip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`rounded-sm border px-2.5 py-1 text-[11px] font-medium transition-colors ${
        active
          ? "border-accent-line bg-accent-soft text-accent"
          : "border-line bg-raised text-ink-muted hover:text-ink"
      }`}
    >
      {children}
    </button>
  );
}

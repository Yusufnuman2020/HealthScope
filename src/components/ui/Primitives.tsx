"use client";
import React from "react";
import { AlertTriangle, Info, RefreshCw } from "lucide-react";

/**
 * Paylaşılan arayüz parçaları.
 *
 * Amaç: her sayfada aynı kart/başlık/uyarı desenlerinin elle yeniden
 * yazılmasını önlemek. Renkler yalnızca anlam taşır — dekoratif renk yok.
 */

// ── Sayfa başlığı ─────────────────────────────────────────────────────────
export function PageHeader({
  title,
  subtitle,
  aside,
}: {
  title: string;
  subtitle?: string;
  aside?: React.ReactNode;
}) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-3 border-b border-line pb-5">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-ink-muted">{subtitle}</p>}
      </div>
      {aside}
    </header>
  );
}

// ── Panel ─────────────────────────────────────────────────────────────────
export function Panel({
  children,
  className = "",
  title,
  description,
  aside,
}: {
  children: React.ReactNode;
  className?: string;
  title?: string;
  description?: string;
  aside?: React.ReactNode;
}) {
  return (
    <section className={`rounded-lg border border-line bg-raised ${title ? "" : "p-5"} ${className}`}>
      {title && (
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-5 py-3.5">
          <div>
            <h2 className="text-sm font-semibold text-ink">{title}</h2>
            {description && <p className="mt-0.5 text-[11px] text-ink-subtle">{description}</p>}
          </div>
          {aside}
        </div>
      )}
      {title ? <div className="p-5">{children}</div> : children}
    </section>
  );
}

// ── Bağlantı durumu ───────────────────────────────────────────────────────
export function StatusDot({
  state,
  label,
  onRetry,
}: {
  state: "checking" | "online" | "offline";
  label?: string;
  onRetry?: () => void;
}) {
  const config = {
    checking: { dot: "bg-ink-subtle animate-pulse", text: "text-ink-subtle", fallback: "Yoklanıyor" },
    online: { dot: "bg-ok", text: "text-ink-muted", fallback: "Çevrimiçi" },
    offline: { dot: "bg-high", text: "text-high", fallback: "Çevrimdışı" },
  }[state];

  return (
    <div
      data-print-hide
      className="inline-flex items-center gap-2 rounded-md border border-line bg-raised px-3 py-1.5"
    >
      <span className={`h-1.5 w-1.5 rounded-full ${config.dot}`} />
      <span className={`text-xs font-medium ${config.text}`}>{label ?? config.fallback}</span>
      {state === "offline" && onRetry && (
        <button
          type="button"
          onClick={onRetry}
          aria-label="Yeniden dene"
          className="text-ink-subtle transition-colors hover:text-ink"
        >
          <RefreshCw size={12} />
        </button>
      )}
    </div>
  );
}

// ── Uyarı kutusu ──────────────────────────────────────────────────────────
const NOTICE_TONES = {
  info: { box: "border-accent-line bg-accent-soft", icon: "text-accent" },
  warn: { box: "border-warn-line bg-warn-soft", icon: "text-warn" },
  danger: { box: "border-high-line bg-high-soft", icon: "text-high" },
  success: { box: "border-ok-line bg-ok-soft", icon: "text-ok" },
} as const;

export type NoticeTone = keyof typeof NOTICE_TONES;

export function Notice({
  tone = "info",
  title,
  children,
  action,
}: {
  tone?: NoticeTone;
  title?: string;
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  const style = NOTICE_TONES[tone];
  const Icon = tone === "info" ? Info : AlertTriangle;
  return (
    <div className={`flex items-start gap-3 rounded-lg border px-4 py-3.5 ${style.box}`}>
      <Icon size={16} className={`mt-0.5 shrink-0 ${style.icon}`} />
      <div className="min-w-0 flex-1 text-[13px] leading-relaxed text-ink">
        {title && <p className="mb-1 font-semibold">{title}</p>}
        <div className="text-ink-muted">{children}</div>
      </div>
      {action}
    </div>
  );
}

// ── Etiket rozeti ─────────────────────────────────────────────────────────
const BADGE_TONES = {
  neutral: "border-line bg-sunken text-ink-muted",
  accent: "border-accent-line bg-accent-soft text-accent",
  high: "border-high-line bg-high-soft text-high",
  low: "border-low-line bg-low-soft text-low",
  ok: "border-ok-line bg-ok-soft text-ok",
  warn: "border-warn-line bg-warn-soft text-warn",
} as const;

export type BadgeTone = keyof typeof BADGE_TONES;

export function Badge({
  tone = "neutral",
  children,
  className = "",
}: {
  tone?: BadgeTone;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-sm border px-1.5 py-0.5 text-[11px] font-medium ${BADGE_TONES[tone]} ${className}`}
    >
      {children}
    </span>
  );
}

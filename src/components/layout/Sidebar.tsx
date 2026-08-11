"use client";
import { Activity, Database, FlaskConical, Menu, Stethoscope, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import ThemeToggle from "./ThemeToggle";

const MENU = [
  { icon: Activity, label: "Genel Bakış", href: "/" },
  { icon: Stethoscope, label: "Kan Analizi", href: "/analysis" },
  { icon: Database, label: "Besin Protokolleri", href: "/food-db" },
  { icon: FlaskConical, label: "Model Durumu", href: "/ai-models" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  const nav = (
    <nav className="space-y-0.5">
      {MENU.map((item) => {
        const active = pathname === item.href;
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={() => setOpen(false)}
            aria-current={active ? "page" : undefined}
            className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors ${
              active
                ? "bg-accent-soft font-semibold text-accent"
                : "text-ink-muted hover:bg-hover hover:text-ink"
            }`}
          >
            <item.icon size={17} strokeWidth={active ? 2.2 : 1.8} />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );

  return (
    <>
      {/* Mobil başlık çubuğu */}
      <div
        data-print-hide
        className="fixed inset-x-0 top-0 z-40 flex items-center justify-between border-b border-line bg-raised px-4 py-3 md:hidden"
      >
        <Brand />
        <div className="flex items-center gap-2">
          <ThemeToggle />
          <button
            type="button"
            onClick={() => setOpen(!open)}
            aria-label={open ? "Menüyü kapat" : "Menüyü aç"}
            aria-expanded={open}
            className="grid h-8 w-8 place-items-center rounded-md border border-line text-ink-muted"
          >
            {open ? <X size={16} /> : <Menu size={16} />}
          </button>
        </div>
      </div>

      {open && (
        <div data-print-hide className="fixed inset-x-0 top-[57px] z-30 border-b border-line bg-raised p-4 md:hidden">
          {nav}
        </div>
      )}

      {/* Masaüstü kenar çubuğu */}
      <aside
        data-print-hide
        className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col justify-between border-r border-line bg-raised p-4 md:flex"
      >
        <div>
          <div className="mb-8 px-1">
            <Brand />
          </div>
          {nav}
        </div>

        <div className="space-y-3 border-t border-line pt-4">
          <ThemeToggle />
          <p className="px-1 text-[11px] leading-relaxed text-ink-subtle">
            Karar destek sistemi. Teşhis aracı değildir.
          </p>
        </div>
      </aside>

    </>
  );
}

function Brand() {
  return (
    <Link href="/" className="flex items-center gap-2.5">
      <span className="grid h-8 w-8 place-items-center rounded-md bg-accent text-white">
        <Stethoscope size={17} strokeWidth={2.2} />
      </span>
      <span className="leading-tight">
        <span className="block text-sm font-semibold tracking-tight text-ink">HealthScope</span>
        <span className="block text-[10px] text-ink-subtle">Klinik Karar Desteği</span>
      </span>
    </Link>
  );
}

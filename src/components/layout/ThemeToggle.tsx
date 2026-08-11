"use client";
import React, { useSyncExternalStore } from "react";
import { Monitor, Moon, Sun } from "lucide-react";

export type ThemeChoice = "light" | "dark" | "system";

export const THEME_STORAGE_KEY = "healthscope-theme";

/**
 * Tema tercihi `localStorage` içinde yaşar — yani React'in dışındaki bir
 * durumdur. Bu yüzden efekt + setState yerine `useSyncExternalStore`
 * kullanılır: sunucu anlık görüntüsü her zaman "system" olduğu için
 * hidrasyon uyuşmazlığı da oluşmaz.
 */
let listeners: Array<() => void> = [];

function subscribe(callback: () => void) {
  listeners.push(callback);
  // Başka sekmede değiştirilirse burası da güncellensin.
  window.addEventListener("storage", callback);
  return () => {
    listeners = listeners.filter((listener) => listener !== callback);
    window.removeEventListener("storage", callback);
  };
}

function getSnapshot(): ThemeChoice {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY);
    return stored === "light" || stored === "dark" ? stored : "system";
  } catch {
    return "system";
  }
}

function getServerSnapshot(): ThemeChoice {
  return "system";
}

/**
 * "system" seçiliyken `data-theme` hiç yazılmaz; globals.css içindeki
 * `prefers-color-scheme` kuralı devreye girer.
 */
function applyTheme(choice: ThemeChoice) {
  const root = document.documentElement;
  if (choice === "system") {
    root.removeAttribute("data-theme");
  } else {
    root.setAttribute("data-theme", choice);
  }
}

const OPTIONS: Array<{ value: ThemeChoice; label: string; icon: typeof Sun }> = [
  { value: "light", label: "Aydınlık", icon: Sun },
  { value: "dark", label: "Koyu", icon: Moon },
  { value: "system", label: "Sistem", icon: Monitor },
];

export default function ThemeToggle() {
  const choice = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  const select = (value: ThemeChoice) => {
    try {
      localStorage.setItem(THEME_STORAGE_KEY, value);
    } catch {
      // Gizli sekmede localStorage yazılamayabilir; tema yine de uygulanır.
    }
    applyTheme(value);
    listeners.forEach((listener) => listener());
  };

  return (
    <div
      role="radiogroup"
      aria-label="Tema"
      data-print-hide
      className="inline-flex items-center gap-0.5 rounded-md border border-line bg-sunken p-0.5"
    >
      {OPTIONS.map((option) => {
        const Icon = option.icon;
        const active = choice === option.value;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={active}
            title={option.label}
            onClick={() => select(option.value)}
            className={`grid h-7 w-7 place-items-center rounded-sm transition-colors ${
              active ? "bg-raised text-accent" : "text-ink-subtle hover:text-ink"
            }`}
          >
            <Icon size={14} />
            <span className="sr-only">{option.label}</span>
          </button>
        );
      })}
    </div>
  );
}

/**
 * Hidrasyondan ÖNCE çalışıp temayı uygulayan betik. Koyu tema tercihiyle
 * açılan sayfanın önce beyaz görünüp sonra kararmasını (FOUC) engeller.
 */
export const themeInitScript = `
(function () {
  try {
    var stored = localStorage.getItem(${JSON.stringify(THEME_STORAGE_KEY)});
    if (stored === "light" || stored === "dark") {
      document.documentElement.setAttribute("data-theme", stored);
    }
  } catch (e) {}
})();
`;
